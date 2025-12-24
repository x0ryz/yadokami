from typing import Awaitable, Callable, Optional

from loguru import logger
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.clients.meta import MetaClient
from src.models import (
    Contact,
    Message,
    MessageDirection,
    MessageStatus,
    WabaPhoneNumber,
)
from src.schemas import MetaMessage, MetaStatus, MetaWebhookPayload
from src.services.whatsapp.media import WhatsAppMediaService


class WhatsAppHandlerService:
    def __init__(
        self,
        session: AsyncSession,
        meta_client: MetaClient,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.session = session
        self.meta_client = meta_client
        self.notifier = notifier
        self.media_service = WhatsAppMediaService(session, meta_client)

    async def _notify(self, event_type: str, data: dict):
        if self.notifier:
            payload = {"event": event_type, "data": data}
            await self.notifier(payload)

    async def process_webhook(self, raw_payload: dict):
        # 1. Валідація через Pydantic
        try:
            webhook = MetaWebhookPayload.model_validate(raw_payload)
        except Exception as e:
            logger.error(f"Failed to validate webhook payload: {e}")
            return

        # 2. Ітерація по структурі
        for entry in webhook.entry:
            for change in entry.changes:
                value = change.value

                # Обробка статусів
                if value.statuses:
                    await self._handle_statuses(value.statuses)

                # Обробка повідомлень
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

        weights = {
            MessageStatus.PENDING: 0,
            MessageStatus.SENT: 1,
            MessageStatus.DELIVERED: 2,
            MessageStatus.READ: 3,
            MessageStatus.FAILED: 4,
        }

        for status in statuses:
            wamid = status.id
            new_status = status_map.get(status.status)

            if not new_status:
                continue

            stmt = (
                select(Message)
                .where(Message.wamid == wamid)
                .options(selectinload(Message.contact))
            )
            db_message = (await self.session.exec(stmt)).first()

            if db_message:
                current_weight = weights.get(db_message.status, -1)
                new_weight = weights.get(new_status, -1)

                if new_weight > current_weight:
                    old_status = db_message.status
                    db_message.status = new_status
                    self.session.add(db_message)

                    await self._notify(
                        "status_update",
                        {
                            "id": str(db_message.id),
                            "wamid": wamid,
                            "old_status": old_status,
                            "new_status": new_status,
                            "phone": db_message.contact.phone_number
                            if db_message.contact
                            else None,
                        },
                    )

        await self.session.commit()

    async def _handle_incoming_messages(
        self, messages: list[MetaMessage], phone_number_id: str
    ):
        # Перевірка нашого WABA номеру
        stmt_phone = select(WabaPhoneNumber).where(
            WabaPhoneNumber.phone_number_id == phone_number_id
        )
        waba_phone = (await self.session.exec(stmt_phone)).first()

        if not waba_phone:
            logger.warning(f"Webhook for unknown phone ID: {phone_number_id}")
            return

        for msg in messages:
            # Дедуплікація
            stmt_dup = select(Message).where(Message.wamid == msg.id)
            if (await self.session.exec(stmt_dup)).first():
                logger.info(f"Message {msg.id} already processed")
                continue

            # Знайти/створити контакт
            stmt_contact = select(Contact).where(Contact.phone_number == msg.from_)
            contact = (await self.session.exec(stmt_contact)).first()

            if not contact:
                contact = Contact(phone_number=msg.from_)
                self.session.add(contact)
                await self.session.commit()
                await self.session.refresh(contact)

            # Витягуємо тіло повідомлення
            body = None
            if msg.type == "text" and msg.text:
                body = msg.text.body
            elif msg.type in ["image", "document", "video"] and getattr(msg, msg.type):
                # Для медіа беремо підпис як тіло
                body = getattr(msg, msg.type).caption

            # Створення повідомлення в БД
            new_msg = Message(
                waba_phone_id=waba_phone.id,
                contact_id=contact.id,
                direction=MessageDirection.INBOUND,
                status=MessageStatus.RECEIVED,
                wamid=msg.id,
                message_type=msg.type,
                body=body,
            )

            self.session.add(new_msg)
            await self.session.commit()
            await self.session.refresh(new_msg)

            # Обробка медіа (делегуємо MediaService)
            media_files_list = []
            if msg.type in ["image", "video", "document", "audio", "voice", "sticker"]:
                media_entry = await self.media_service.process_media_attachment(
                    new_msg, msg
                )

                if media_entry:
                    # Одразу генеруємо URL для фронтенду
                    url = await self.media_service.storage_service.get_presigned_url(
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

            # Сповіщення через WS
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
