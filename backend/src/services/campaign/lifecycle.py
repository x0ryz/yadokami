from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    Campaign,
    CampaignStatus,
    get_utc_now,
)
from src.models.campaigns import CampaignContact
from src.repositories.campaign import CampaignRepository
from src.services.notifications.service import NotificationService


class CampaignLifecycleManager:
    """Manages campaign lifecycle states and transitions."""

    def __init__(
        self,
        session: AsyncSession,
        campaigns_repo: CampaignRepository,
        notifier: NotificationService,
    ):
        self.session = session
        self.campaigns = campaigns_repo
        self.notifier = notifier

    async def start_campaign(self, campaign: Campaign):
        """Start a campaign and initialize tracking."""
        self._validate_can_start(campaign)

        now = get_utc_now()
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = now
        campaign.updated_at = now
        self.session.add(campaign)

        await self.session.commit()
        logger.info(f"Campaign {campaign.id} started")

        # Notify
        await self.notifier.notify_campaign_status(
            campaign_id=campaign.id,
            status="running",
            name=campaign.name,
            started_at=now.isoformat(),
        )

    async def pause_campaign(self, campaign: Campaign):
        """Pause a running campaign."""
        campaign.status = CampaignStatus.PAUSED
        campaign.updated_at = get_utc_now()
        self.session.add(campaign)
        await self.session.commit()

        logger.info(f"Campaign {campaign.id} paused")

        await self.notifier.notify_campaign_status(
            campaign_id=campaign.id,
            status="paused",
            name=campaign.name,
        )

    async def resume_campaign(self, campaign: Campaign):
        """Resume a paused campaign."""
        logger.info(f"Resuming campaign {campaign.id} from status {campaign.status}")
        campaign.status = CampaignStatus.RUNNING
        campaign.updated_at = get_utc_now()
        self.session.add(campaign)
        await self.session.flush()  # Ensure changes are written to DB
        await self.session.commit()
        await self.session.refresh(campaign)

        logger.info(f"Campaign {campaign.id} resumed with status {campaign.status}")

        await self.notifier.notify_campaign_status(
            campaign_id=campaign.id,
            status="running",
            name=campaign.name,
        )

    async def complete_campaign(self, campaign: Campaign):
        """Mark campaign as completed and notify."""
        now = get_utc_now()

        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = now
        campaign.updated_at = now
        self.session.add(campaign)
        await self.session.commit()

        logger.info(f"Campaign {campaign.id} completed")

        stats = await self.campaigns.get_stats_by_id(campaign.id)

        # Notify
        await self.notifier.notify_campaign_status(
            campaign_id=campaign.id,
            status="completed",
            name=campaign.name,
            total=stats["total_contacts"],
            sent=stats["sent_count"],
            delivered=stats["delivered_count"],
            failed=stats["failed_count"],
            completed_at=now.isoformat(),
        )

    async def check_and_complete_if_done(self, campaign_id: UUID):
        """Check if campaign is completed and update status if so."""
        campaign = await self.campaigns.get_by_id(campaign_id)

        if not campaign:
            logger.debug(f"Campaign {campaign_id} not found")
            return

        if campaign.status not in [CampaignStatus.RUNNING, CampaignStatus.PAUSED]:
            logger.debug(
                f"Campaign {campaign_id} is {campaign.status}, not checking completion"
            )
            return

        stmt = select(func.count()).where(
            CampaignContact.campaign_id == campaign_id,
            CampaignContact.message_id.is_(None),
        )

        remaining = (await self.session.execute(stmt)).scalar() or 0

        if remaining > 0:
            logger.debug(
                f"Campaign {campaign_id}: still {remaining} contacts waiting for processing. "
                f"Not completing yet."
            )
            return

        logger.info(f"Completing campaign {campaign_id}: all contacts processed.")

        await self.complete_campaign(campaign)

    @staticmethod
    def _validate_can_start(campaign: Campaign):
        """Validate that campaign can be started."""
        if campaign.status not in [
            CampaignStatus.DRAFT,
            CampaignStatus.SCHEDULED,
            CampaignStatus.RUNNING,
            CampaignStatus.PAUSED,
        ]:
            raise ValueError(f"Cannot start campaign in {campaign.status} status")
