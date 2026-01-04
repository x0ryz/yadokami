import uuid

from loguru import logger
from src.clients.meta import MetaClient
from src.core.uow import UnitOfWork
from src.models import Contact, Message, MessageDirection, MessageStatus
from src.schemas import WhatsAppMessage
from src.services.notifications.service import NotificationService


class MessageSenderService:
    """
    Message sending service.

    IMPORTANT: This service manages transactions.
    Each public method commits its changes.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        meta_client: MetaClient,
        notifier: NotificationService,
    ):
        self.uow = uow
        self.meta_client = meta_client
        self.notifier = notifier

    async def send_manual_message(self, message: WhatsAppMessage):
        """
        Send a manual message (from API).
        This method manages its own transaction.
        """
        async with self.uow:
            contact = await self.uow.contacts.get_or_create(message.phone_number)

            template_id = None
            template_name = None

            if message.type == "template":
                template = await self.uow.templates.get_active_by_id(message.body)
                if template:
                    template_id = template.id
                    template_name = template.name
                else:
                    logger.error(f"Template {message.body} not found")
                    return

            await self._send_and_commit(
                contact=contact,
                message_type=message.type,
                body=message.body,
                template_id=template_id,
                template_name=template_name,
                is_campaign=False,
            )

    async def send_to_contact(
        self,
        contact: Contact,
        message_type: str,
        body: str,
        template_id: uuid.UUID | None = None,
        template_name: str | None = None,
        is_campaign: bool = False,
    ) -> Message:
        """
        Send message to a contact.
        IMPORTANT: This method does NOT commit.
        The caller must commit the transaction.
        """
        waba_phone = await self.uow.waba.get_default_phone()
        if not waba_phone:
            raise ValueError("No WABA Phone numbers found in DB.")

        # Create message entity
        message = await self.uow.messages.create(
            waba_phone_id=waba_phone.id,
            contact_id=contact.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            message_type=message_type,
            body=body if message_type == "text" else template_name,
            template_id=template_id,
        )

        await self.uow.session.flush()
        await self.uow.session.refresh(message)

        contact.updated_at = message.created_at
        contact.last_message_at = message.created_at
        contact.last_message_id = message.id
        self.uow.session.add(contact)

        if not is_campaign:
            await self.notifier.notify_new_message(message, phone=contact.phone_number)

            preview_body = (
                body
                if message_type == "text"
                else (template_name or f"Sent {message_type}")
            )

            await self.notifier._publish(
                {
                    "event": "contact_updated",
                    "data": {
                        "id": str(contact.id),
                        "phone_number": contact.phone_number,
                        "unread_count": contact.unread_count,
                        "last_message_at": contact.last_message_at.isoformat(),
                        "last_message_body": preview_body,
                        "last_message_type": message_type,
                        "last_message_status": "pending",
                        "last_message_direction": "outbound",
                    },
                    "timestamp": message.created_at.isoformat(),
                }
            )

        try:
            # Send to Meta
            payload = self._build_payload(
                to_phone=contact.phone_number,
                message_type=message_type,
                body=body,
                template_name=template_name,
            )

            result = await self.meta_client.send_message(
                waba_phone.phone_number_id, payload
            )
            wamid = result.get("messages", [{}])[0].get("id")

            if not wamid:
                raise Exception("No WAMID in Meta response")

            # Update message with WAMID
            message.wamid = wamid
            message.status = MessageStatus.SENT
            self.uow.session.add(message)

            logger.info(f"Message sent to {contact.phone_number}. WAMID: {wamid}")

            if not is_campaign:
                await self.notifier.notify_message_status(
                    message_id=message.id,
                    wamid=wamid,
                    status="sent",
                    phone=contact.phone_number,
                )

            return message

        except Exception as e:
            logger.error(f"Failed to send to {contact.phone_number}: {e}")
            message.status = MessageStatus.FAILED
            self.uow.session.add(message)
            raise

    async def _send_and_commit(
        self,
        contact: Contact,
        message_type: str,
        body: str,
        template_id: uuid.UUID | None,
        template_name: str | None,
        is_campaign: bool,
    ):
        try:
            await self.send_to_contact(
                contact=contact,
                message_type=message_type,
                body=body,
                template_id=template_id,
                template_name=template_name,
                is_campaign=is_campaign,
            )
            await self.uow.commit()
        except Exception:
            await self.uow.commit()
            raise

    def _build_payload(
        self, to_phone: str, message_type: str, body: str, template_name: str | None
    ) -> dict:
        """Build WhatsApp API payload."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": message_type,
        }
        if message_type == "text":
            payload["text"] = {"body": body}
        elif message_type == "template":
            if not template_name:
                raise ValueError("Template name required")
            payload["template"] = {
                "name": template_name,
                "language": {"code": "en_US"},
            }
        return payload
