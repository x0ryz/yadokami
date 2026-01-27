from datetime import datetime
from uuid import UUID

from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import selectinload

from src.models import (
    Campaign,
    CampaignContact,
    CampaignStatus,
    get_utc_now,
)
from src.models.base import MessageStatus
from src.models.messages import Message
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

    async def get_stats_by_id(self, campaign_id: UUID) -> dict | None:
        """
        Отримує детальну статистику для однієї кампанії.
        """
        stmt = (
            select(
                Campaign,
                func.count(CampaignContact.id).label("total_contacts"),
                func.count(case((Message.status == MessageStatus.SENT, 1))).label(
                    "sent_count"
                ),
                func.count(case((Message.status == MessageStatus.DELIVERED, 1))).label(
                    "delivered_count"
                ),
                func.count(case((Message.status == MessageStatus.READ, 1))).label(
                    "read_count"
                ),
                func.count(case((Message.status == MessageStatus.FAILED, 1))).label(
                    "failed_count"
                ),
                func.count(case((CampaignContact.is_replied == True, 1))).label(
                    "replied_count"
                ),
            )
            .select_from(Campaign)
            .outerjoin(CampaignContact, Campaign.id == CampaignContact.campaign_id)
            .outerjoin(Message, CampaignContact.message_id == Message.id)
            .where(Campaign.id == campaign_id)  # <--- Фільтруємо по ID
            .group_by(Campaign.id)
        )

        result = await self.session.execute(stmt)
        row = result.first()

        if not row:
            return None



        campaign, total, sent, delivered, read, failed, replied = row

        camp_dict = {
            c.name: getattr(campaign, c.name) for c in campaign.__table__.columns
        }

        # Обчислюємо message_type
        if campaign.template_id:
            camp_dict["message_type"] = "template"
        else:
            camp_dict["message_type"] = "text"

        camp_dict.update(
            {
                "total_contacts": total,
                "sent_count": sent,
                "delivered_count": delivered,
                "read_count": read,
                "failed_count": failed,
                "replied_count": replied,
            }
        )

        return camp_dict

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
        stmt = select(Campaign).order_by(desc(Campaign.updated_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_basic(self, status: CampaignStatus | None = None) -> list[Campaign]:
        stmt = select(Campaign).order_by(Campaign.created_at.desc())

        if status:
            stmt = stmt.where(Campaign.status == status)

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
        self, campaign_id: UUID, limit: int = 500, offset: int = 0
    ) -> list[CampaignContact]:
        stmt = (
            select(CampaignContact)
            .where(
                CampaignContact.campaign_id == campaign_id,
                CampaignContact.message_id.is_(None),
            )
            .options(selectinload(CampaignContact.contact))
            .with_for_update(skip_locked=True)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_campaign_contacts(
        self, campaign_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[CampaignContact]:
        stmt = (
            select(CampaignContact)
            .where(CampaignContact.campaign_id == campaign_id)
            .options(
                selectinload(CampaignContact.contact),
                selectinload(CampaignContact.message),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self, campaign_id: UUID, status: MessageStatus) -> int:
        stmt = (
            select(func.count())
            .select_from(CampaignContact)
            .join(CampaignContact.message)
            .where(
                CampaignContact.campaign_id == campaign_id,
                Message.status == status,
            )
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
        stmt = select(func.count()).where(CampaignContact.campaign_id == campaign_id)
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

    async def update(
        self, campaign_contact_id: UUID, **kwargs
    ) -> CampaignContact | None:
        """Update campaign contact."""
        campaign_contact = await self.get_by_id(campaign_contact_id)
        if not campaign_contact:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(campaign_contact, key):
                setattr(campaign_contact, key, value)

        campaign_contact.updated_at = get_utc_now()
        self.session.add(campaign_contact)
        await self.session.flush()
        await self.session.refresh(campaign_contact)
        return campaign_contact

    async def delete_by_id(self, campaign_contact_id: UUID) -> bool:
        """Delete campaign contact by id."""
        campaign_contact = await self.get_by_id(campaign_contact_id)
        if not campaign_contact:
            return False

        await self.session.delete(campaign_contact)
        await self.session.flush()
        return True
