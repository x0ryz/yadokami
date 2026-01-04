from loguru import logger
from src.core.uow import UnitOfWork
from src.models import MessageDirection, MessageStatus, get_utc_now
from src.schemas import MetaMessage, MetaStatus, MetaWebhookPayload
from src.services.media.service import MediaService
from src.services.notifications.service import NotificationService


class MessageProcessorService:
    def __init__(
        self,
        uow: UnitOfWork,
        media_service: MediaService,
        notifier: NotificationService,
    ):
        self.uow = uow
        self.media = media_service
        self.notifier = notifier

    async def process_webhook(self, webhook: MetaWebhookPayload):
        """Маршрутизація подій вебхука"""
        for entry in webhook.entry:
            for change in entry.changes:
                value = change.value

                if value.statuses:
                    await self._handle_statuses(value.statuses)

                if value.messages:
                    phone_id = value.metadata.get("phone_number_id")
                    await self._handle_messages(value.messages, phone_id)

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
                if not db_message:
                    continue

                if self._is_newer_status(db_message.status, new_status):
                    db_message.status = new_status
                    self.uow.session.add(db_message)

                    await self.notifier.notify_message_status(
                        message_id=db_message.id,
                        wamid=status.id,
                        status=status.status,
                        phone=db_message.contact.phone_number
                        if db_message.contact
                        else None,
                    )

            await self.uow.commit()

    async def _handle_messages(self, messages: list[MetaMessage], phone_number_id: str):
        waba_phone_db_id = None
        async with self.uow:
            waba_phone = await self.uow.waba.get_by_phone_id(phone_number_id)
            if waba_phone:
                waba_phone_db_id = waba_phone.id

        if not waba_phone_db_id:
            logger.warning(f"Unknown phone ID: {phone_number_id}")
            return

        for msg in messages:
            async with self.uow:
                if await self.uow.messages.get_by_wamid(msg.id):
                    logger.info(f"Message {msg.id} deduplicated")
                    continue

                contact = await self.uow.contacts.get_or_create(msg.from_)
                contact.unread_count += 1
                contact.updated_at = get_utc_now()
                self.uow.session.add(contact)

                body = None
                if msg.type == "text":
                    body = msg.text.body
                elif hasattr(msg, msg.type):
                    media_obj = getattr(msg, msg.type)
                    if hasattr(media_obj, "caption"):
                        body = media_obj.caption

                new_msg = await self.uow.messages.create(
                    waba_phone_id=waba_phone_db_id,
                    contact_id=contact.id,
                    direction=MessageDirection.INBOUND,
                    status=MessageStatus.RECEIVED,
                    wamid=msg.id,
                    message_type=msg.type,
                    body=body,
                )

                await self.uow.session.flush()

                if msg.type in [
                    "image",
                    "video",
                    "document",
                    "audio",
                    "voice",
                    "sticker",
                ]:
                    await self.media.handle_media_attachment(new_msg.id, msg)
                    await self.uow.session.flush()

                # ВИПРАВЛЕННЯ: refresh викликається завжди, для всіх типів повідомлень
                await self.uow.session.refresh(new_msg, ["media_files"])

                await self.uow.commit()

                media_dtos = []
                # Тепер це безпечно, бо media_files завантажено
                if new_msg.media_files:
                    for mf in new_msg.media_files:
                        url = await self.media.storage.get_presigned_url(mf.r2_key)
                        media_dtos.append(
                            {
                                "id": str(mf.id),
                                "file_name": mf.file_name,
                                "file_mime_type": mf.file_mime_type,
                                "url": url,
                                "caption": mf.caption,
                            }
                        )

                await self.notifier.notify_new_message(
                    new_msg,
                    phone=contact.phone_number,
                    media_files=media_dtos,
                )

                await self.notifier._publish(
                    {
                        "event": "contact_unread_changed",
                        "data": {
                            "contact_id": str(contact.id),
                            "phone": contact.phone_number,
                            "unread_count": contact.unread_count,
                        },
                        "timestamp": get_utc_now().isoformat(),
                    }
                )

    def _is_newer_status(self, old: MessageStatus, new: MessageStatus) -> bool:
        weights = {
            MessageStatus.PENDING: 0,
            MessageStatus.SENT: 1,
            MessageStatus.DELIVERED: 2,
            MessageStatus.READ: 3,
            MessageStatus.FAILED: 4,
        }
        return weights.get(new, -1) > weights.get(old, -1)
