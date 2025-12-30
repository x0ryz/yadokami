from typing import Awaitable, Callable, Optional

from loguru import logger

from src.clients.meta import MetaClient
from src.core.uow import UnitOfWork
from src.models import MessageDirection, MessageStatus, get_utc_now
from src.schemas import MetaMessage, MetaStatus, MetaWebhookPayload
from src.services.storage import StorageService
from src.services.whatsapp.media import WhatsAppMediaService


class WhatsAppHandlerService:
    def __init__(
        self,
        uow: UnitOfWork,
        meta_client: MetaClient,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.uow = uow
        self.meta_client = meta_client
        self.notifier = notifier
        self.storage_service = StorageService()

    async def _notify(self, event_type: str, data: dict):
        if self.notifier:
            payload = {"event": event_type, "data": data}
            await self.notifier(payload)

    async def process_webhook(self, raw_payload: dict):
        try:
            webhook = MetaWebhookPayload.model_validate(raw_payload)
        except Exception as e:
            logger.error(f"Failed to validate webhook payload: {e}")
            return

        for entry in webhook.entry:
            for change in entry.changes:
                value = change.value

                if value.statuses:
                    await self._handle_statuses(value.statuses)

                if value.messages:
                    phone_number_id = value.metadata.get("phone_number_id")
                    await self._handle_incoming_messages(
                        value.messages, phone_number_id
                    )

    async def _handle_statuses(self, statuses: list[MetaStatus]):
        status_map = {
            "sent": MessageStatus.SENT,
            "delivered": MessageStatus.DELIVERED,
            "read": MessageStatus.READ,
            "failed": MessageStatus.FAILED,
        }

        async with self.uow:
            for status in statuses:
                new_status = status_map.get(status.status)
                if not new_status:
                    continue

                db_message = await self.uow.messages.get_by_wamid(status.id)

                if db_message:
                    old_status = db_message.status

                    if self._is_newer_status(old_status, new_status):
                        db_message.status = new_status
                        self.uow.session.add(db_message)

                        if new_status == MessageStatus.FAILED and status.errors:
                            logger.error(f"Message {status.id} failed: {status.errors}")

                        await self._notify(
                            "status_update",
                            {
                                "id": str(db_message.id),
                                "wamid": status.id,
                                "old_status": old_status,
                                "new_status": new_status,
                                "phone": db_message.contact.phone_number
                                if db_message.contact
                                else None,
                            },
                        )

    async def _handle_incoming_messages(
        self, messages: list[MetaMessage], phone_number_id: str
    ):
        waba_phone_db_id = None
        async with self.uow:
            waba_phone = await self.uow.waba.get_by_phone_id(phone_number_id)
            if waba_phone:
                waba_phone_db_id = waba_phone.id

        if not waba_phone_db_id:
            logger.warning(f"Webhook for unknown phone ID: {phone_number_id}")
            return

        for msg in messages:
            async with self.uow:
                if await self.uow.messages.get_by_wamid(msg.id):
                    logger.info(f"Message {msg.id} already processed")
                    continue

                contact = await self.uow.contacts.get_or_create(msg.from_)

                contact.unread_count += 1
                contact.updated_at = get_utc_now()
                self.uow.session.add(contact)

                body = None
                if msg.type == "text" and msg.text:
                    body = msg.text.body
                elif msg.type in ["image", "document", "video"] and getattr(
                    msg, msg.type
                ):
                    body = getattr(msg, msg.type).caption

                new_msg = await self.uow.messages.create(
                    auto_flush=True,
                    waba_phone_id=waba_phone.id,
                    contact_id=contact.id,
                    direction=MessageDirection.INBOUND,
                    status=MessageStatus.RECEIVED,
                    wamid=msg.id,
                    message_type=msg.type,
                    body=body,
                )

                media_files_list = []
                if msg.type in [
                    "image",
                    "video",
                    "document",
                    "audio",
                    "voice",
                    "sticker",
                ]:
                    media_service = WhatsAppMediaService(
                        self.uow, self.meta_client, self.storage_service
                    )
                    media_entry = await media_service.process_media_attachment(
                        new_msg, msg
                    )

                    if media_entry:
                        url = await media_service.storage_service.get_presigned_url(
                            media_entry.r2_key
                        )
                        media_files_list.append(
                            {
                                "id": str(media_entry.id),
                                "file_name": media_entry.file_name,
                                "file_mime_type": media_entry.file_mime_type,
                                "url": url,
                                "caption": media_entry.caption,
                            }
                        )

                msg_data = {
                    "id": str(new_msg.id),
                    "from": msg.from_,
                    "type": new_msg.message_type,
                    "body": new_msg.body,
                    "wamid": new_msg.wamid,
                    "created_at": new_msg.created_at.isoformat(),
                    "media_files": media_files_list,
                }
                await self._notify("new_message", msg_data)

    def _is_newer_status(
        self, old_status: MessageStatus, new_status: MessageStatus
    ) -> bool:
        weights = {
            MessageStatus.PENDING: 0,
            MessageStatus.SENT: 1,
            MessageStatus.DELIVERED: 2,
            MessageStatus.READ: 3,
            MessageStatus.FAILED: 4,
        }
        return weights.get(new_status, -1) > weights.get(old_status, -1)
