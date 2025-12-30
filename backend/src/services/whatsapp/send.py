from typing import Awaitable, Callable, Optional

from loguru import logger

from src.clients.meta import MetaClient
from src.core.uow import UnitOfWork
from src.models import (
    MessageDirection,
    MessageStatus,
)
from src.schemas import WhatsAppMessage


class WhatsAppSenderService:
    def __init__(
        self,
        uow: UnitOfWork,
        meta_client: MetaClient,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.uow = uow
        self.meta_client = meta_client
        self.notifier = notifier

    async def _notify(self, event_type: str, data: dict):
        if self.notifier:
            payload = {"event": event_type, "data": data}
            await self.notifier(payload)

    def _build_payload(
        self, message: WhatsAppMessage, template_name: str | None = None
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.phone_number,
            "type": message.type,
        }

        if message.type == "text":
            payload["text"] = {"body": message.body}

        elif message.type == "template":
            if not template_name:
                raise ValueError("Template name is required for template messages")

            payload["template"] = {
                "name": template_name,
                "language": {"code": "en_US"},
            }

        return payload

    async def send_outbound_message(self, message: WhatsAppMessage):
        async with self.uow:
            contact = await self.uow.contacts.get_or_create(message.phone_number)
            waba_phone = await self.uow.waba.get_default_phone()

            if not waba_phone:
                logger.error("No WABA Phone numbers found in DB.")
                return

            template_db_id = None
            template_real_name = None

            if message.type == "template":
                requested_template_id = message.body

                template_obj = await self.uow.templates.get_active_by_id(
                    requested_template_id
                )

                if not template_obj:
                    logger.error(
                        f"Template with ID {requested_template_id} not found or not APPROVED"
                    )
                    return

                template_db_id = template_obj.id
                template_real_name = template_obj.name

            body_to_save = (
                template_real_name if message.type == "template" else message.body
            )

            db_message = await self.uow.messages.create(
                auto_flush=True,
                waba_phone_id=waba_phone.id,
                contact_id=contact.id,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.PENDING,
                message_type=message.type,
                body=body_to_save,
                template_id=template_db_id,
            )

            await self._notify(
                "new_message",
                {
                    "id": str(db_message.id),
                    "phone": message.phone_number,
                    "direction": "outbound",
                    "status": "pending",
                    "body": body_to_save,
                    "created_at": db_message.created_at.isoformat(),
                },
            )

            try:
                payload = self._build_payload(message, template_name=template_real_name)

                result = await self.meta_client.send_message(
                    waba_phone.phone_number_id, payload
                )
                wamid = result.get("messages", [{}])[0].get("id")

                if wamid:
                    self.uow.messages.mark_as_sent(db_message, wamid)

                    await self._notify(
                        "status_update",
                        {
                            "id": str(db_message.id),
                            "wamid": wamid,
                            "old_status": "pending",
                            "new_status": "sent",
                            "phone": message.phone_number,
                        },
                    )
                    logger.success(
                        f"Message sent to {message.phone_number}. WAMID: {wamid}"
                    )

            except Exception as e:
                logger.exception(f"Failed to send message to {message.phone_number}")
                self.uow.messages.mark_as_failed(db_message)
