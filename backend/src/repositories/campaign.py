from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload
from src.models import (
    Campaign,
    CampaignContact,
    CampaignDeliveryStatus,
    CampaignStatus,
    get_utc_now,
)
from src.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session):
        super().__init__(session, Campaign)

    async def create(self, **kwargs) -> Campaign:
        campaign = Campaign(**kwargs)
        self.session.add(campaign)
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign

    async def get_by_id_with_template(self, campaign_id: UUID) -> Campaign | None:
        stmt = (
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .options(selectinload(Campaign.template))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_scheduled_campaigns(self, now: datetime) -> list[Campaign]:
        stmt = select(Campaign).where(
            Campaign.status == CampaignStatus.SCHEDULED, Campaign.scheduled_at <= now
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_status(
        self, status: CampaignStatus | None = None
    ) -> list[Campaign]:
        stmt = select(Campaign)
        if status:
            stmt = stmt.where(Campaign.status == status)

        stmt = stmt.order_by(
            Campaign.scheduled_at.desc(),
            Campaign.created_at.desc(),
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_stats(
        self,
        campaign_id: UUID,
        sent_delta: int = 0,
        delivered_delta: int = 0,
        failed_delta: int = 0,
    ):
        campaign = await self.get_by_id(campaign_id)
        if campaign:
            campaign.sent_count += sent_delta
            campaign.delivered_count += delivered_delta
            campaign.failed_count += failed_delta
            campaign.updated_at = get_utc_now()
            self.session.add(campaign)

    async def count_total(self) -> int:
        stmt = select(func.count()).select_from(Campaign)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_by_global_status(self, status: CampaignStatus) -> int:
        stmt = select(func.count()).where(Campaign.status == status)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_recent(self, limit: int) -> list[Campaign]:
        stmt = select(Campaign).order_by(
            desc(Campaign.updated_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CampaignContactRepository(BaseRepository[CampaignContact]):
    def __init__(self, session):
        super().__init__(session, CampaignContact)

    async def create(self, **kwargs) -> CampaignContact:
        link = CampaignContact(**kwargs)
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def bulk_create(self, links: list[CampaignContact]):
        self.session.add_all(links)
        await self.session.flush()

    async def get_sendable_contacts(
        self, campaign_id: UUID, limit: int = 500
    ) -> list[CampaignContact]:
        stmt = (
            select(CampaignContact)
            .where(
                CampaignContact.campaign_id == campaign_id,
                CampaignContact.status == CampaignDeliveryStatus.QUEUED,
            )
            .options(selectinload(CampaignContact.contact))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_campaign_contacts(
        self, campaign_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[CampaignContact]:
        stmt = (
            select(CampaignContact)
            .where(CampaignContact.campaign_id == campaign_id)
            .options(selectinload(CampaignContact.contact))
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(
        self, campaign_id: UUID, status: CampaignDeliveryStatus
    ) -> int:
        stmt = select(func.count()).where(
            CampaignContact.campaign_id == campaign_id, CampaignContact.status == status
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def exists_for_contact(self, campaign_id: UUID, contact_id: UUID) -> bool:
        stmt = (
            select(1)
            .where(
                CampaignContact.campaign_id == campaign_id,
                CampaignContact.contact_id == contact_id,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar() is not None

    async def count_all(self, campaign_id: UUID) -> int:
        stmt = select(func.count()).where(
            CampaignContact.campaign_id == campaign_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_by_message_id(self, message_id: UUID) -> CampaignContact | None:
        stmt = (
            select(CampaignContact)
            .where(CampaignContact.message_id == message_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar()
