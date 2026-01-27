from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import MessageStatus
from src.repositories.message import MessageRepository
from src.schemas import MetaStatus
from src.services.notifications.service import NotificationService


class StatusHandler:
    """Handles message status updates from WhatsApp webhook."""

    def __init__(
        self,
        session: AsyncSession,
        notifier: NotificationService,
    ):
        self.session = session
        self.notifier = notifier
        self.messages = MessageRepository(session)

    async def handle(self, statuses: list[MetaStatus]):
        """Process status updates for messages."""
        status_map = {
            "sent": MessageStatus.SENT,
            "delivered": MessageStatus.DELIVERED,
            "read": MessageStatus.READ,
            "failed": MessageStatus.FAILED,
        }

        notifications_to_send = []

        for status in statuses:
            new_status = status_map.get(status.status)
            if not new_status:
                continue

            # 1. Шукаємо повідомлення
            # Важливо: переконайся, що get_by_wamid підтягує contact (joinedload),
            # інакше message.contact.phone_number викличе додатковий запит або помилку
            db_message = await self.messages.get_by_wamid(status.id)

            if not db_message:
                logger.debug(
                    f"Message with wamid {status.id} not found, skipping update."
                )
                continue

            # 2. Оновлюємо, тільки якщо новий статус "старший"
            if self._is_newer_status(db_message.status, new_status):
                db_message.status = new_status

                # --- ДОДАНО: Збереження помилок від Meta ---
                if new_status == MessageStatus.FAILED and status.errors:
                    error_obj = status.errors[0]  # Беремо першу помилку
                    db_message.error_code = error_obj.get("code")
                    db_message.error_message = error_obj.get("title") or error_obj.get("message")
                    logger.warning(
                        f"Message {db_message.id} failed: {db_message.error_message}"
                    )
                # -------------------------------------------

                self.messages.add(db_message)


                # Prepare notification data
                notifications_to_send.append(
                    {
                        "message_id": db_message.id,
                        "wamid": status.id,
                        "status": status.status,
                        "phone": db_message.contact.phone_number
                        if db_message.contact
                        else None,
                        "error": db_message.error_message
                        if new_status == MessageStatus.FAILED
                        else None,
                    }
                )

        # Commit transaction explicitly
        await self.session.commit()

        # Send notifications after commit
        for note in notifications_to_send:
            await self.notifier.notify_message_status(**note)

    def _is_newer_status(self, old: MessageStatus, new: MessageStatus) -> bool:
        """Check if the new status is a progression from the old status."""
        weights = {
            MessageStatus.PENDING: 0,
            MessageStatus.SENT: 1,
            MessageStatus.DELIVERED: 2,
            MessageStatus.READ: 3,
            MessageStatus.FAILED: 4,
        }
        # FAILED має найвищий пріоритет, його не можна перезаписати на READ/DELIVERED
        return weights.get(new, -1) > weights.get(old, -1)
