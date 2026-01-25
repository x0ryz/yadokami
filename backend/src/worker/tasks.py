import asyncio

from sqlalchemy import select

from src.core.database import async_session_maker
from src.models import CampaignStatus, Message, MessageStatus, get_utc_now
from src.repositories.campaign import CampaignRepository
from src.services.campaign.lifecycle import CampaignLifecycleManager
from src.services.notifications.service import NotificationService
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

                # Check for scheduled campaigns to start
                campaigns = await campaigns_repo.get_scheduled_campaigns(now)
                for campaign in campaigns:
                    logger.info(
                        f"Triggering scheduled campaign: {campaign.id}")
                    await broker.publish(
                        str(campaign.id),
                        subject="campaigns.start",
                        stream="campaigns",
                    )

                # Check for running/paused campaigns that might need completion
                running_campaigns = await campaigns_repo.list_with_status(CampaignStatus.RUNNING)
                paused_campaigns = await campaigns_repo.list_with_status(CampaignStatus.PAUSED)

                all_active = running_campaigns + paused_campaigns
                if all_active:
                    logger.debug(
                        f"Checking completion for {len(all_active)} active campaigns")

                for campaign in all_active:
                    try:
                        # Use a fresh session for each campaign check
                        async with async_session_maker() as check_session:
                            check_campaigns_repo = CampaignRepository(
                                check_session)
                            notifier = NotificationService()
                            lifecycle = CampaignLifecycleManager(
                                check_session, check_campaigns_repo, notifier, {}
                            )
                            await lifecycle.check_and_complete_if_done(campaign.id)
                            await check_session.commit()
                    except Exception as e:
                        logger.error(
                            f"Error checking completion for campaign {campaign.id}: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Scheduled campaigns checker stopped")
            break
        except Exception as e:
            logger.error(f"Error in scheduled campaigns checker: {e}")


async def scheduled_messages_checker(broker):
    """
    Background task that checks for scheduled messages periodically.
    Replaces the standalone scheduler.py service.
    """
    logger.info("Scheduled messages checker started")
    while True:
        try:
            # Check every 10 seconds
            await asyncio.sleep(10)
            
            async with async_session_maker() as session:
                now = get_utc_now()
                
                # Find messages that are scheduled and due to be sent
                stmt = (
                    select(Message.id)
                    .where(
                        Message.scheduled_at.isnot(None),
                        Message.scheduled_at <= now,
                        Message.status == MessageStatus.PENDING,
                    )
                    .limit(100)  # Process in batches
                )
                
                result = await session.execute(stmt)
                message_ids = result.scalars().all()
                
                if message_ids:
                    logger.info(f"Found {len(message_ids)} scheduled messages ready to send")
                    
                    for message_id in message_ids:
                        # Publish event for each message
                        # We use 'messages.send_scheduled_item' subject
                        await broker.publish(
                            {"message_id": str(message_id)},
                            subject="messages.send_scheduled_item",
                        )

        except asyncio.CancelledError:
            logger.info("Scheduled messages checker stopped")
            break
        except Exception as e:
            logger.error(f"Error in scheduled messages checker: {e}")
