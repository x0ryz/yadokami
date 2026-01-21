from sqlalchemy.ext.asyncio import AsyncSession

from src.models import MessageStatus
from src.repositories.message import MessageRepository
from src.schemas import MetaStatus
from src.services.campaign.tracker import CampaignTrackerService
from src.services.notifications.service import NotificationService


class StatusHandler:
    """Handles message status updates from WhatsApp webhook."""

    def __init__(
        self,
        session: AsyncSession,
        notifier: NotificationService,
        campaign_tracker: CampaignTrackerService,
    ):
        self.session = session
        self.notifier = notifier
        self.campaign_tracker = campaign_tracker

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

            db_message = await self.messages.get_by_wamid(status.id)
            if not db_message:
                continue

            if self._is_newer_status(db_message.status, new_status):
                db_message.status = new_status
                self.messages.add(db_message)

                await self.campaign_tracker.update_on_status_change(
                    db_message.id, new_status
                )

                # Prepare notification data
                notifications_to_send.append(
                    {
                        "message_id": db_message.id,
                        "wamid": status.id,
                        "status": status.status,
                        "phone": db_message.contact.phone_number
                        if db_message.contact
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
        return weights.get(new, -1) > weights.get(old, -1)
