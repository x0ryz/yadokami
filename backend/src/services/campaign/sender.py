from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Campaign
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
from src.repositories.template import TemplateRepository
from src.services.campaign.executor import CampaignMessageExecutor
from src.services.campaign.lifecycle import CampaignLifecycleManager
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

        # Initialize repositories
        campaigns_repo = CampaignRepository(session)
        campaign_contacts_repo = CampaignContactRepository(session)
        contacts_repo = ContactRepository(session)
        template_repo = TemplateRepository(session)

        # Initialize sub-services
        self.lifecycle = CampaignLifecycleManager(session, campaigns_repo, notifier)
        self.executor = CampaignMessageExecutor(
            session,
            campaigns_repo,
            campaign_contacts_repo,
            contacts_repo,
            template_repo,
            message_sender,
            notifier,
        )
        self.campaigns = campaigns_repo

    # ==================== Public API ====================

    async def start_campaign(self, campaign_id: UUID):
        """Start a campaign."""
        campaign = await self._get_campaign_or_raise(campaign_id)
        await self.lifecycle.start_campaign(campaign)

    async def send_single_message(
        self, campaign_id: UUID, link_id: UUID, contact_id: UUID
    ) -> bool:
        """Send a single message to a contact as part of a campaign.
        Returns True if sent successfully, False otherwise.
        """
        success = False
        try:
            success = await self.executor.send_message(campaign_id, link_id, contact_id)
        except Exception as e:
            logger.warning(f"Failed to send campaign message to {contact_id}: {e}")
            await self.executor.handle_send_failure(campaign_id, link_id, str(e))
            success = False
        finally:
            await self.lifecycle.check_and_complete_if_done(campaign_id)
        return success

    async def pause_campaign(self, campaign_id: UUID):
        """Pause a running campaign."""
        campaign = await self._get_campaign_or_raise(campaign_id)
        await self.lifecycle.pause_campaign(campaign)

    async def resume_campaign(self, campaign_id: UUID):
        """Resume a paused campaign."""
        campaign = await self._get_campaign_or_raise(campaign_id)
        await self.lifecycle.resume_campaign(campaign)

    # ==================== Helper Methods ====================

    async def _get_campaign_or_raise(self, campaign_id: UUID) -> Campaign:
        """Get campaign by ID or raise ValueError."""
        campaign = await self.campaigns.get_by_id_with_template(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        return campaign
