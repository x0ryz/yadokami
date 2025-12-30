import json
from uuid import UUID

import httpx
from aiolimiter import AsyncLimiter
from redis import asyncio as aioredis
from taskiq import Context, TaskiqDepends

from src.clients.meta import MetaClient
from src.core.broker import broker
from src.core.config import settings
from src.core.database import async_session_maker
from src.core.logger import setup_logging
from src.core.uow import UnitOfWork
from src.models import WebhookLog, get_utc_now
from src.schemas import WabaSyncRequest, WebhookEvent, WhatsAppMessage
from src.services.campaign import CampaignSenderService
from src.services.sync import SyncService
from src.services.websocket import BatchProgressEvent
from src.services.whatsapp import WhatsAppService

logger = setup_logging()

limiter = AsyncLimiter(10, 1)


async def get_http_client(context: Context = TaskiqDepends()) -> httpx.AsyncClient:
    return context.state.http_client


async def publish_ws_update(data: dict):
    """Publish WebSocket updates to Redis Pub/Sub (for frontend)"""
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        message_json = json.dumps(data, default=str)
        await redis.publish("ws_updates", message_json)
        await redis.close()
    except Exception as e:
        logger.error(f"Failed to publish WS update: {e}")


@broker.task(task_name="handle_messages")
async def handle_messages_task(
    message: WhatsAppMessage, client: httpx.AsyncClient = TaskiqDepends(get_http_client)
):
    """Handle individual WhatsApp message requests (API endpoint)"""
    with logger.contextualize(request_id=message.request_id):
        uow = UnitOfWork(async_session_maker)
        meta_client = MetaClient(client)
        service = WhatsAppService(uow, meta_client, notifier=publish_ws_update)
        await service.send_outbound_message(message)


@broker.task(task_name="sync_account_data")
async def handle_account_sync_task(
    message: WabaSyncRequest, client: httpx.AsyncClient = TaskiqDepends(get_http_client)
):
    """Handle WABA account sync requests"""
    with logger.contextualize(request_id=message.request_id):
        async with async_session_maker() as session:
            meta_client = MetaClient(client)
            sync_service = SyncService(session, meta_client)
            await sync_service.sync_account_data()


@broker.task(task_name="raw_webhooks")
async def handle_raw_webhook_task(
    event: WebhookEvent, client: httpx.AsyncClient = TaskiqDepends(get_http_client)
):
    """Handle incoming webhooks from Meta"""
    data = event.payload
    async with async_session_maker() as session:
        try:
            log_entry = WebhookLog(payload=data)
            session.add(log_entry)
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to save webhook log: {e}")

    try:
        uow = UnitOfWork(async_session_maker)
        meta_client = MetaClient(client)
        service = WhatsAppService(uow, meta_client, notifier=publish_ws_update)
        await service.process_webhook(data)
    except Exception:
        logger.exception("Error processing webhook in service")


@broker.task(task_name="process_campaign_batch")
async def process_campaign_batch_task(
    campaign_id: str,
    batch_number: int = 1,
    client: httpx.AsyncClient = TaskiqDepends(get_http_client),
):
    """
    Process a batch of contacts with detailed progress tracking.

    Sends WebSocket notifications:
    - When batch starts
    - Progress within batch (every N messages)
    - When batch completes
    - Aggregate campaign progress
    """
    BATCH_SIZE = 100
    PROGRESS_UPDATE_INTERVAL = 10

    uow = UnitOfWork(async_session_maker)
    meta_client = MetaClient(client)
    sender = CampaignSenderService(uow, meta_client, notifier=publish_ws_update)

    # Get contacts for this batch
    async with uow:
        contacts = await uow.campaign_contacts.get_sendable_contacts(
            UUID(campaign_id), limit=BATCH_SIZE
        )

    if not contacts:
        # No more contacts, check if campaign is complete
        await sender._check_campaign_completion(UUID(campaign_id))
        return

    batch_size = len(contacts)
    logger.info(
        f"Batch #{batch_number}: Processing {batch_size} contacts "
        f"for campaign {campaign_id}"
    )

    # Notify batch start
    await sender._notify_event(
        BatchProgressEvent(
            campaign_id=UUID(campaign_id),
            batch_number=batch_number,
            batch_size=batch_size,
            processed=0,
            successful=0,
            failed=0,
        )
    )

    processed = 0
    successful = 0
    failed = 0

    for idx, link in enumerate(contacts, start=1):
        async with limiter:
            try:
                await sender.send_single_message(
                    campaign_id=UUID(campaign_id),
                    link_id=link.id,
                    contact_id=link.contact_id,
                )
                successful += 1

            except Exception as e:
                logger.error(f"Error sending in batch: {e}")
                failed += 1

            processed += 1

            # Send progress update every N messages
            if processed % PROGRESS_UPDATE_INTERVAL == 0 or processed == batch_size:
                await sender.notify_batch_progress(
                    campaign_id=UUID(campaign_id),
                    batch_number=batch_number,
                    batch_size=batch_size,
                    processed=processed,
                    successful=successful,
                    failed=failed,
                )

    logger.info(
        f"Batch #{batch_number} completed: {successful} successful, {failed} failed"
    )

    # Queue next batch
    await process_campaign_batch_task.kiq(campaign_id, batch_number + 1)


@broker.task(task_name="campaign_start")
async def handle_campaign_start_task(
    campaign_id: str, client: httpx.AsyncClient = TaskiqDepends(get_http_client)
):
    """Start processing a campaign"""
    with logger.contextualize(campaign_id=campaign_id):
        logger.info(f"Starting campaign {campaign_id}")
        try:
            uow = UnitOfWork(async_session_maker)
            meta_client = MetaClient(client)
            sender = CampaignSenderService(uow, meta_client, notifier=publish_ws_update)

            await sender.start_campaign(UUID(campaign_id))

            # Start first batch
            await process_campaign_batch_task.kiq(campaign_id, batch_number=1)

        except Exception as e:
            logger.exception(f"Campaign {campaign_id} failed to start")

            # Notify failure
            from src.services.websocket import CampaignStatusEvent

            event = CampaignStatusEvent(
                campaign_id=UUID(campaign_id), status="FAILED", error=str(e)
            )
            await publish_ws_update(event.to_dict())


@broker.task(task_name="campaign_resume")
async def handle_campaign_resume_task(
    campaign_id: str, client: httpx.AsyncClient = TaskiqDepends(get_http_client)
):
    """Resume a paused campaign"""
    with logger.contextualize(campaign_id=campaign_id):
        logger.info(f"Task: Resuming campaign {campaign_id}")
        try:
            uow = UnitOfWork(async_session_maker)
            meta_client = MetaClient(client)
            sender = CampaignSenderService(uow, meta_client, notifier=publish_ws_update)

            await sender.resume_campaign(UUID(campaign_id))

            await process_campaign_batch_task.kiq(campaign_id)

        except Exception:
            logger.exception(f"Campaign {campaign_id} resume failed")


@broker.task(schedule=[{"cron": "* * * * *"}])
async def check_scheduled_campaigns_task():
    """Background task that checks for scheduled campaigns and starts them."""
    now = get_utc_now()
    uow = UnitOfWork(async_session_maker)

    async with uow:
        campaigns = await uow.campaigns.get_scheduled_campaigns(now)
        for campaign in campaigns:
            try:
                logger.info(f"Scheduler: Triggering campaign {campaign.id}")
                await handle_campaign_start_task.kiq(str(campaign.id))
            except Exception as e:
                logger.error(f"Failed to trigger campaign {campaign.id}: {e}")
