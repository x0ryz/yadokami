from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Campaign
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
from src.services.campaign.executor import CampaignMessageExecutor
from src.services.campaign.lifecycle import CampaignLifecycleManager
from src.services.campaign.tracker import CampaignProgressTracker
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService


class CampaignSenderService:
    """
    Main service for managing campaign message sending.
    Acts as a facade coordinating lifecycle and execution.
    """

    def __init__(
        self,
        session: AsyncSession,
        message_sender: MessageSenderService,
        notifier: NotificationService,
    ):
        self.session = session
        self.trackers: dict[str, CampaignProgressTracker] = {}

        # Initialize repositories
        campaigns_repo = CampaignRepository(session)
        campaign_contacts_repo = CampaignContactRepository(session)
        contacts_repo = ContactRepository(session)

        # Initialize sub-services
        self.lifecycle = CampaignLifecycleManager(
            session, campaigns_repo, notifier, self.trackers
        )
        self.executor = CampaignMessageExecutor(
            session,
            campaigns_repo,
            campaign_contacts_repo,
            contacts_repo,
            message_sender,
            notifier,
            self.trackers,
        )
        self.campaigns = campaigns_repo

    # ==================== Public API ====================

    async def start_campaign(self, campaign_id: UUID):
        """Start a campaign."""
        campaign = await self._get_campaign_or_raise(campaign_id)
        await self.lifecycle.start_campaign(campaign)
        await self.executor._notify_progress(campaign)

    async def send_single_message(
        self, campaign_id: UUID, link_id: UUID, contact_id: UUID
    ):
        """Send a single message to a contact as part of a campaign."""
        try:
            await self.executor.send_message(campaign_id, link_id, contact_id)
        except Exception as e:
            logger.exception(f"Failed to send campaign message to {contact_id}")
            await self.executor.handle_send_failure(campaign_id, link_id, str(e))
        finally:
            await self.lifecycle.check_and_complete_if_done(campaign_id)

    async def pause_campaign(self, campaign_id: UUID):
        """Pause a running campaign."""
        campaign = await self._get_campaign_or_raise(campaign_id)
        await self.lifecycle.pause_campaign(campaign)

    async def resume_campaign(self, campaign_id: UUID):
        """Resume a paused campaign."""
        campaign = await self._get_campaign_or_raise(campaign_id)
        await self.lifecycle.resume_campaign(campaign)

    async def notify_batch_progress(
        self, campaign_id: UUID, batch_number: int, stats: dict
    ):
        """Notify about batch processing progress."""
        # Could be moved to notifier if needed
        pass

    # ==================== Helper Methods ====================

    async def _get_campaign_or_raise(self, campaign_id: UUID) -> Campaign:
        """Get campaign by ID or raise ValueError."""
        campaign = await self.campaigns.get_by_id_with_template(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        return campaign
