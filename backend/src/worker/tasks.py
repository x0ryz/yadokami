import asyncio

from src.core.database import async_session_maker
from src.models import get_utc_now
from src.repositories.campaign import CampaignRepository
from src.worker.dependencies import logger


async def scheduled_campaigns_checker(broker):
    """Background task that checks for scheduled campaigns every minute"""
    logger.info("Scheduled campaigns checker started")
    while True:
        try:
            await asyncio.sleep(60)
            logger.debug("Checking for scheduled campaigns...")
            now = get_utc_now()
            async with async_session_maker() as session:
                campaigns_repo = CampaignRepository(session)
                campaigns = await campaigns_repo.get_scheduled_campaigns(now)
                for campaign in campaigns:
                    logger.info(f"Triggering scheduled campaign: {campaign.id}")
                    await broker.publish(
                        str(campaign.id),
                        subject="campaigns.start",
                        stream="campaigns",
                    )
        except asyncio.CancelledError:
            logger.info("Scheduled campaigns checker stopped")
            break
        except Exception as e:
            logger.error(f"Error in scheduled campaigns checker: {e}")
