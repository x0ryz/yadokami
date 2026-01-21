from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas import MetaWebhookPayload
from src.services.campaign.tracker import CampaignTrackerService
from src.services.media.service import MediaService
from src.services.messaging.handlers import (
    IncomingMessageHandler,
    StatusHandler,
    SystemEventHandler,
)
from src.services.notifications.service import NotificationService


class MessageProcessorService:
    """
    Webhook event dispatcher.
    """

    def __init__(
        self,
        session: AsyncSession,
        media_service: MediaService,
        notifier: NotificationService,
    ):
        self.session = session

        self.campaign_tracker = CampaignTrackerService(session)

        self.incoming_handler = IncomingMessageHandler(session, media_service, notifier)

        self.status_handler = StatusHandler(session, notifier, self.campaign_tracker)

        self.system_handler = SystemEventHandler(session, notifier)

    async def process_webhook(self, webhook: MetaWebhookPayload):
        """
        Process incoming webhook by routing to appropriate handlers.
        """
        for entry in webhook.entry:
            waba_id = entry.id

            for change in entry.changes:
                value = change.value

                # Route system events
                if value.message_template_status_update:
                    await self.system_handler.handle_template_update(
                        value.message_template_status_update
                    )

                if value.account_review_update:
                    await self.system_handler.handle_account_review(
                        waba_id, value.account_review_update
                    )

                if value.phone_number_quality_update:
                    await self.system_handler.handle_phone_quality(
                        value.phone_number_quality_update
                    )

                # Route incoming messages
                if value.messages:
                    phone_id = value.metadata.get("phone_number_id")
                    if phone_id:
                        await self.incoming_handler.handle(value.messages, phone_id)

                # Route status updates
                if value.statuses:
                    await self.status_handler.handle(value.statuses)
