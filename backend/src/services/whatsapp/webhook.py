from typing import Awaitable, Callable, Optional

from loguru import logger
from src.core.uow import UnitOfWork
from src.models import MessageStatus, get_utc_now
from src.schemas import MetaMessage, MetaStatus, MetaWebhookPayload
from src.services.storage import StorageService
from src.services.whatsapp.messaging import WhatsAppMessagingService


class WhatsAppWebhookService:
    """
    Чистий сервіс для обробки вебхуків.
    Приймає валідовані Pydantic моделі, маршрутизує події
    та делегує роботу MessagingService.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        messaging_service: WhatsAppMessagingService,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.uow = uow
        self.messaging = messaging_service
        self.notifier = notifier
        self.storage = StorageService()

    async def process_payload(self, webhook: MetaWebhookPayload):
        """Головна точка входу. Приймає вже валідований Pydantic об'єкт."""
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
        """Обробка статусів (delivered, read, failed)."""
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
                if not db_message:
                    continue

                if self._is_newer_status(db_message.status, new_status):
                    db_message.status = new_status
                    self.uow.session.add(db_message)

                    if new_status == MessageStatus.FAILED and status.errors:
                        logger.error(f"Message {status.id} failed: {status.errors}")

                    await self._notify(
                        "status_update",
                        {
                            "id": str(db_message.id),
                            "wamid": status.id,
                            "old_status": db_message.status,
                            "new_status": new_status,
                            "phone": db_message.contact.phone_number
                            if db_message.contact
                            else None,
                        },
                    )
            await self.uow.commit()

    async def _handle_incoming_messages(
        self, messages: list[MetaMessage], phone_number_id: str
    ):
        """Обробка вхідних повідомлень."""
        # Знаходимо WABA телефон
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
                # Дедуплікація
                if await self.uow.messages.get_by_wamid(msg.id):
                    logger.info(f"Message {msg.id} already processed")
                    continue

                # Оновлення контакту
                contact = await self.uow.contacts.get_or_create(msg.from_)
                contact.unread_count += 1
                contact.updated_at = get_utc_now()
                self.uow.session.add(contact)

                # Делегуємо створення повідомлення та обробку медіа в MessagingService
                new_msg = await self.messaging.handle_incoming_message_content(
                    msg, contact.id, waba_phone_db_id
                )

                await self.uow.commit()

                # Refresh to get all relationships including media_files
                await self.uow.session.refresh(new_msg, ["media_files"])

                # Prepare media files for notification
                media_list = []
                for media_file in new_msg.media_files:
                    try:
                        # Generate presigned URL for each media file
                        url = await self.storage.get_presigned_url(media_file.r2_key)
                        media_list.append(
                            {
                                "id": str(media_file.id),
                                "file_name": media_file.file_name,
                                "file_mime_type": media_file.file_mime_type,
                                "url": url,
                                "caption": media_file.caption,
                            }
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to generate URL for media {media_file.id}: {e}"
                        )

                # Формуємо дані для нотифікації фронтенду
                msg_data = {
                    "id": str(new_msg.id),
                    "from": msg.from_,
                    "type": new_msg.message_type,
                    "body": new_msg.body,
                    "wamid": new_msg.wamid,
                    "created_at": new_msg.created_at.isoformat(),
                    "media_files": media_list,
                }

                await self._notify("new_message", msg_data)
                logger.info(
                    f"Message {new_msg.id} processed with {len(media_list)} media files"
                )

    async def _notify(self, event_type: str, data: dict):
        if self.notifier:
            await self.notifier({"event": event_type, "data": data})

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
