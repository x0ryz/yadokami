from uuid import UUID

from loguru import logger
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import (
    CampaignContact,
    CampaignStatus,
    Campaign
)
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.services.notifications.service import NotificationService


class CampaignTrackerService:
    """
    Manages campaign response tracking.
    """

    def __init__(
        self,
        session: AsyncSession,
        notifier: NotificationService,
    ):
        self.session = session
        self.notifier = notifier
        self.campaign_contacts = CampaignContactRepository(session)
        self.campaigns = CampaignRepository(session)

    async def handle_reply(self, contact_id: UUID):
        """
        Handle a reply from a contact.
        Identify the relevant campaign and mark it as replied.
        """
        # Find the most recent campaign sent to this contact
        # We look for campaign contacts where is_replied is False
        stmt = (
            select(CampaignContact)
            .join(Campaign)
            .where(
                CampaignContact.contact_id == contact_id,
                CampaignContact.is_replied == False,
                # Optionally filter for recent campaigns only?
                # For now, let's take the most recent one.
            )
            .order_by(desc(CampaignContact.created_at))
            .limit(1)
            .options(selectinload(CampaignContact.campaign))
        )
        
        result = await self.session.execute(stmt)
        campaign_contact = result.scalars().first()
        
        if not campaign_contact:
            # No unreplied campaign found for this contact
            return

        # Mark as replied
        campaign_contact.is_replied = True
        self.session.add(campaign_contact)
        await self.session.commit()
        
        logger.info(f"Marked campaign {campaign_contact.campaign_id} as replied for contact {contact_id}")
        
        # Notify progress update (stats will change)
        stats = await self.campaigns.get_stats_by_id(campaign_contact.campaign_id)
        if stats:
             await self.notifier.notify_campaign_progress(
                campaign_id=campaign_contact.campaign_id,
                **stats
            )
