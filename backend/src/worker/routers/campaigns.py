import asyncio
import json
from uuid import UUID

from faststream import Depends
from faststream.nats import NatsRouter

from src.core.broker import broker
from src.core.database import async_session_maker
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.models import CampaignStatus
from src.services.campaign.sender import CampaignSenderService
from src.worker.dependencies import (
    get_campaign_sender_service,
    limiter,
    logger,
)

router = NatsRouter()

# Manage per-campaign pull consumers so we can fully pause fetching
campaign_consumers: dict[str, asyncio.Task] = {}


async def consume_campaign_messages(
    campaign_id: str,
    service: CampaignSenderService,
):
    """Pull-based consumption for a specific campaign subject.
    Stops fetching when task is cancelled (e.g., on pause).
    """
    subject = f"campaigns.send.{campaign_id}"
    durable = f"campaign-sender-{campaign_id}"
    try:
        js = broker._connection.jetstream()
        psub = await js.pull_subscribe(subject, durable)
        logger.info(f"Started pull consumer for {subject}")
    except Exception as e:
        logger.error(f"Failed to start pull consumer for {campaign_id}: {e}")
        return

    batch_size = 10
    empty_fetches = 0
    processed_count_for_stats = 0
    try:
        while True:
            try:
                messages = await psub.fetch(batch=batch_size, timeout=1.0)
                if not messages:
                    empty_fetches += 1
                    # After several empty fetches, check if campaign should complete
                    if empty_fetches >= 3:
                        camp = await service.lifecycle.check_and_complete_if_done(UUID(campaign_id))
                        if camp and camp.status in [CampaignStatus.COMPLETED, CampaignStatus.FAILED]:
                            raise asyncio.CancelledError()
                        empty_fetches = 0
                    continue
                empty_fetches = 0
            except TimeoutError:
                empty_fetches += 1
                if empty_fetches >= 3:
                    # No messages for a while; check completion
                    camp = await service.lifecycle.check_and_complete_if_done(UUID(campaign_id))
                    if camp and camp.status in [CampaignStatus.COMPLETED, CampaignStatus.FAILED]:
                         raise asyncio.CancelledError()
                    empty_fetches = 0
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Error fetching campaign {campaign_id} messages: {e}")
                await asyncio.sleep(0.5)
                continue

            for msg in messages:
                try:
                    payload = json.loads(msg.data.decode())
                except Exception:
                    await msg.ack()
                    continue

                # Basic payload validation
                cid = payload.get("campaign_id") or campaign_id
                link_id = payload.get("link_id")
                contact_id = payload.get("contact_id")
                if not (cid and link_id and contact_id):
                    await msg.ack()
                    continue

                # Check campaign is still RUNNING before processing
                async with async_session_maker() as session:
                    try:
                        campaigns_repo = CampaignRepository(session)
                        campaign = await campaigns_repo.get_by_id(UUID(cid))
                        if not campaign:
                            logger.debug(f"Campaign {cid} not found")
                            await msg.ack()
                            continue
                        
                        # Only stop consumer for PAUSED campaigns
                        # For COMPLETED, we continue to ack remaining messages
                        if campaign.status == CampaignStatus.PAUSED:
                            logger.debug(f"Halting consumer; campaign is paused")
                            await msg.ack()
                            raise asyncio.CancelledError()
                        
                        # For non-RUNNING (e.g., COMPLETED), just ack and skip
                        if campaign.status != CampaignStatus.RUNNING:
                            logger.debug(
                                f"Skipping message; campaign status={campaign.status}")
                            await msg.ack()
                            
                            if campaign.status in [CampaignStatus.COMPLETED, CampaignStatus.FAILED]:
                                logger.info(f"Campaign {cid} is finished ({campaign.status}), stopping consumer")
                                raise asyncio.CancelledError()
                                
                            continue
                    finally:
                        # Ensure session is explicitly closed
                        await session.close()

                # Process send
                async with limiter:
                    try:
                        success = await service.send_single_message(
                            campaign_id=UUID(cid),
                            link_id=UUID(link_id),
                            contact_id=UUID(contact_id),
                        )
                        await msg.ack()

                        processed_count_for_stats += 1
                        if processed_count_for_stats >= 5:
                            processed_count_for_stats = 0
                            try:
                                async with async_session_maker() as stats_session:
                                    stats_repo = CampaignRepository(stats_session)
                                    stats = await stats_repo.get_stats_by_id(UUID(cid))
                                    if stats:
                                        total = stats.get("total_contacts", 0)
                                        sent = stats.get("sent_count", 0)
                                        delivered = stats.get("delivered_count", 0)
                                        failed = stats.get("failed_count", 0)
                                        read = stats.get("read_count", 0)
                                        
                                        percent = 0
                                        if total > 0:
                                            processed_items = sent + failed
                                            percent = int((processed_items / total) * 100)
                                        
                                        await service.lifecycle.notifier.notify_campaign_progress(
                                            campaign_id=UUID(cid),
                                            total=total,
                                            sent=sent,
                                            delivered=delivered,
                                            read=read,
                                            failed=failed,
                                            progress_percent=percent
                                        )
                            except Exception as e:
                                logger.error(f"Failed to send progress update: {e}")

                        if not success:
                            logger.debug(
                                f"Send failed/skipped for contact {contact_id}"
                            )
                    except Exception as e:
                        logger.exception(f"Failed to send: {e}")
                        await msg.ack()
                        # continue processing

    except asyncio.CancelledError:
        logger.info(f"Stopped pull consumer for {subject}")
    except Exception as e:
        logger.error(f"Consumer for {campaign_id} errored: {e}")
    finally:
        # Final completion check when consumer exits
        try:
            # Don't check if we know it's already done to avoid spam logs
            # We can't easily know status here without querying DB again, 
            # but usually check_and_complete_if_done handles checks. 
            # Since we fixed the infinite loop, one extra check is fine.
            await service.lifecycle.check_and_complete_if_done(UUID(campaign_id))
        except Exception as e:
            logger.warning(
                f"Final completion check failed for {campaign_id}: {e}")


# Push-based send subscriber removed; using per-campaign pull consumers instead


@router.subscriber("campaigns.start", stream="campaigns", durable="campaign-starter")
async def handle_campaign_start(
    campaign_id: str,
    service: CampaignSenderService = Depends(get_campaign_sender_service),
):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            logger.info(f"Starting campaign {campaign_id}")
            await service.start_campaign(UUID(campaign_id))

            # Give DB time to propagate status change to other sessions
            await asyncio.sleep(0.5)

            batch_size = 100
            offset = 0
            while True:
                # Stop publishing if campaign is no longer RUNNING
                async with async_session_maker() as check_session:
                    try:
                        campaigns_repo = CampaignRepository(check_session)
                        campaign = await campaigns_repo.get_by_id(UUID(campaign_id))
                        should_stop = not campaign or campaign.status != CampaignStatus.RUNNING
                    finally:
                        await check_session.close()

                    if should_stop:
                        logger.info(
                            f"Halting start publish; campaign status={campaign.status if campaign else 'unknown'}"
                        )
                        break

                async with async_session_maker() as session:
                    try:
                        repo = CampaignContactRepository(session)
                        contacts = await repo.get_sendable_contacts(
                            UUID(campaign_id), limit=batch_size, offset=offset
                        )
                    finally:
                        await session.close()

                if not contacts:
                    break

                for link in contacts:
                    await broker.publish(
                        {
                            "campaign_id": campaign_id,
                            "link_id": str(link.id),
                            "contact_id": str(link.contact_id),
                        },
                        subject=f"campaigns.send.{campaign_id}",
                        stream="campaigns",
                    )
                offset += len(contacts)

            logger.info(f"Campaign started. Tasks published: {offset}")
            # Start pull-based consumer for this campaign
            existing = campaign_consumers.get(campaign_id)
            if existing and not existing.done():
                existing.cancel()
                try:
                    await existing
                except Exception:
                    pass
            campaign_consumers[campaign_id] = asyncio.create_task(
                consume_campaign_messages(campaign_id, service)
            )
        except Exception as e:
            logger.exception(f"Start failed: {e}")


@router.subscriber("campaigns.resume", stream="campaigns", durable="campaign-resumer")
async def handle_campaign_resume(
    campaign_id: str,
    service: CampaignSenderService = Depends(get_campaign_sender_service),
):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            logger.info(f"Resuming campaign {campaign_id}")
            await service.resume_campaign(UUID(campaign_id))

            # Give DB time to propagate status change to other sessions
            await asyncio.sleep(0.5)

            batch_size = 100
            offset = 0
            while True:
                # Stop publishing if campaign is no longer RUNNING
                async with async_session_maker() as check_session:
                    try:
                        campaigns_repo = CampaignRepository(check_session)
                        campaign = await campaigns_repo.get_by_id(UUID(campaign_id))
                        should_stop = not campaign or campaign.status != CampaignStatus.RUNNING
                    finally:
                        await check_session.close()

                    if should_stop:
                        logger.info(
                            f"Halting resume publish; campaign status={campaign.status if campaign else 'unknown'}"
                        )
                        break

                # Get remaining QUEUED contacts
                async with async_session_maker() as session:
                    try:
                        repo = CampaignContactRepository(session)
                        contacts = await repo.get_sendable_contacts(
                            UUID(campaign_id), limit=batch_size, offset=offset
                        )
                    finally:
                        await session.close()

                if not contacts:
                    break

                for link in contacts:
                    await broker.publish(
                        {
                            "campaign_id": campaign_id,
                            "link_id": str(link.id),
                            "contact_id": str(link.contact_id),
                        },
                        subject=f"campaigns.send.{campaign_id}",
                        stream="campaigns",
                    )
                offset += len(contacts)

            logger.info(f"Campaign resumed. Tasks published: {offset}")
            # Start or restart pull-based consumer for this campaign
            existing = campaign_consumers.get(campaign_id)
            if existing and not existing.done():
                existing.cancel()
                try:
                    await existing
                except Exception:
                    pass
            campaign_consumers[campaign_id] = asyncio.create_task(
                consume_campaign_messages(campaign_id, service)
            )
        except Exception as e:
            logger.exception(f"Resume failed: {e}")


@router.subscriber("campaigns.pause", stream="campaigns", durable="campaign-pauser")
async def handle_campaign_pause(
    campaign_id: str,
    service: CampaignSenderService = Depends(get_campaign_sender_service),
):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            logger.info(f"Pausing campaign {campaign_id}")
            await service.pause_campaign(UUID(campaign_id))
            # Stop pull-based consumer if running
            existing = campaign_consumers.get(campaign_id)
            if existing and not existing.done():
                existing.cancel()
                try:
                    await existing
                except Exception:
                    pass
                logger.info(
                    f"Stopped consumer for paused campaign {campaign_id}")
        except Exception as e:
            logger.exception(f"Pause failed: {e}")
