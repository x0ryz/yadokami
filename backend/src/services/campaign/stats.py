"""Service for updating campaign statistics based on message status changes."""

import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CampaignDeliveryStatus, MessageStatus
from src.repositories.campaign import CampaignContactRepository, CampaignRepository


class CampaignStatsService:
    """Manages campaign delivery statistics and status updates."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.campaigns = CampaignRepository(session)
        self.campaign_contacts = CampaignContactRepository(session)

    async def update_on_status_change(
        self, message_id: uuid.UUID, new_status: MessageStatus
    ) -> None:
        """
        Update campaign statistics when a message status changes.
        """
        campaign_link = await self.campaign_contacts.get_by_message_id(message_id)

        if not campaign_link:
            return  # Not a campaign message

        # Don't update if already marked as replied
        if campaign_link.status == CampaignDeliveryStatus.REPLIED:
            return

        campaign = await self.campaigns.get_by_id(campaign_link.campaign_id)
        if not campaign:
            logger.warning(f"Campaign {campaign_link.campaign_id} not found")
            return

        # Update campaign counters based on status transition
        if new_status == MessageStatus.DELIVERED:
            await self._handle_delivered(campaign, campaign_link)
        elif new_status == MessageStatus.READ:
            await self._handle_read(campaign, campaign_link)
        elif new_status == MessageStatus.FAILED:
            await self._handle_failed(campaign, campaign_link)

        self.campaigns.add(campaign)
        self.campaign_contacts.add(campaign_link)

    async def _handle_delivered(self, campaign, campaign_link):
        """Handle transition to DELIVERED status."""
        if campaign_link.status in [
            CampaignDeliveryStatus.READ,
            CampaignDeliveryStatus.FAILED,
            CampaignDeliveryStatus.DELIVERED,
        ]:
            return

        # Декрементуємо попередній статус
        if campaign_link.status == CampaignDeliveryStatus.SENT:
            campaign.sent_count = max(0, campaign.sent_count - 1)

        campaign_link.status = CampaignDeliveryStatus.DELIVERED
        campaign.delivered_count += 1

    async def _handle_read(self, campaign, campaign_link):
        """Handle transition to READ status."""
        if campaign_link.status == CampaignDeliveryStatus.READ:
            return

        # Декрементуємо попередній статус
        if campaign_link.status == CampaignDeliveryStatus.DELIVERED:
            campaign.delivered_count = max(0, campaign.delivered_count - 1)
        elif campaign_link.status == CampaignDeliveryStatus.SENT:
            campaign.sent_count = max(0, campaign.sent_count - 1)

        campaign_link.status = CampaignDeliveryStatus.READ
        campaign.read_count += 1

    async def _handle_failed(self, campaign, campaign_link):
        """Handle transition to FAILED status."""
        if campaign_link.status == CampaignDeliveryStatus.FAILED:
            return

        # Декрементуємо попередній статус
        if campaign_link.status == CampaignDeliveryStatus.READ:
            campaign.read_count = max(0, campaign.read_count - 1)
        elif campaign_link.status == CampaignDeliveryStatus.DELIVERED:
            campaign.delivered_count = max(0, campaign.delivered_count - 1)
        elif campaign_link.status == CampaignDeliveryStatus.SENT:
            campaign.sent_count = max(0, campaign.sent_count - 1)

        campaign_link.status = CampaignDeliveryStatus.FAILED
        campaign.failed_count += 1
