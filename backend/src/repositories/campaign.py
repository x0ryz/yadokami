from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.models import (
    Campaign,
    CampaignContact,
    CampaignStatus,
    ContactStatus,
    get_utc_now,
)
from src.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session):
        super().__init__(session, Campaign)

    async def create(self, **kwargs) -> Campaign:
        """Create a new campaign"""
        campaign = Campaign(**kwargs)
        self.session.add(campaign)
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign

    async def get_by_id_with_template(self, campaign_id: UUID) -> Campaign | None:
        """Get campaign with template relationship loaded"""
        stmt = (
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .options(selectinload(Campaign.template))
        )
        result = await self.session.exec(stmt)
        return result.first()

    async def get_scheduled_campaigns(self, now: datetime) -> list[Campaign]:
        """Get all campaigns scheduled to run at or before now"""
        stmt = select(Campaign).where(
            Campaign.status == CampaignStatus.SCHEDULED, Campaign.scheduled_at <= now
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def list_with_status(
        self, status: CampaignStatus | None = None
    ) -> list[Campaign]:
        """List campaigns filtered by status and sorted by schedule/create time"""
        stmt = select(Campaign)
        if status:
            stmt = stmt.where(Campaign.status == status)

        stmt = stmt.order_by(
            Campaign.scheduled_at.desc(),
            Campaign.created_at.desc(),
        )

        result = await self.session.exec(stmt)
        return list(result.all())

    async def update_stats(
        self,
        campaign_id: UUID,
        sent_delta: int = 0,
        delivered_delta: int = 0,
        failed_delta: int = 0,
    ):
        """Update campaign statistics"""
        campaign = await self.get_by_id(campaign_id)
        if campaign:
            campaign.sent_count += sent_delta
            campaign.delivered_count += delivered_delta
            campaign.failed_count += failed_delta
            campaign.updated_at = get_utc_now()
            self.session.add(campaign)


class CampaignContactRepository(BaseRepository[CampaignContact]):
    def __init__(self, session):
        super().__init__(session, CampaignContact)

    async def create(self, **kwargs) -> CampaignContact:
        """Create a new campaign-contact link"""
        link = CampaignContact(**kwargs)
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def bulk_create(self, links: list[CampaignContact]):
        """Bulk insert campaign-contact links"""
        self.session.add_all(links)
        await self.session.flush()

    async def get_sendable_contacts(
        self, campaign_id: UUID, limit: int = 500
    ) -> list[CampaignContact]:
        """Get contacts ready to be sent (respecting 24h window)"""
        stmt = (
            select(CampaignContact)
            .where(
                CampaignContact.campaign_id == campaign_id,
                CampaignContact.status == ContactStatus.NEW,
            )
            .options(selectinload(CampaignContact.contact))
            .limit(limit)
        )

        result = await self.session.exec(stmt)
        return list(result.all())

    async def get_campaign_contacts(
        self, campaign_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[CampaignContact]:
        """Get all contacts for a campaign with pagination"""
        stmt = (
            select(CampaignContact)
            .where(CampaignContact.campaign_id == campaign_id)
            .options(selectinload(CampaignContact.contact))
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.exec(stmt)
        return list(result.all())

    async def count_by_status(self, campaign_id: UUID, status: ContactStatus) -> int:
        """Count contacts in campaign by status"""
        stmt = select(CampaignContact).where(
            CampaignContact.campaign_id == campaign_id, CampaignContact.status == status
        )
        result = await self.session.exec(stmt)
        return len(list(result.all()))

    async def exists_for_contact(self, campaign_id: UUID, contact_id: UUID) -> bool:
        """Check if contact is already in campaign"""
        stmt = select(CampaignContact).where(
            CampaignContact.campaign_id == campaign_id,
            CampaignContact.contact_id == contact_id,
        )
        result = await self.session.exec(stmt)
        return result.first() is not None

    async def count_all(self, campaign_id: UUID) -> int:
        """Count all contacts in campaign"""
        stmt = select(CampaignContact).where(
            CampaignContact.campaign_id == campaign_id)
        result = await self.session.exec(stmt)
        return len(list(result.all()))
