import mimetypes
import os
import uuid
from uuid import UUID

import aiofiles
import httpx
from aiolimiter import AsyncLimiter
from src.clients.meta import MetaClient
from src.core.broker import broker
from src.core.config import settings
from src.core.database import async_session_maker
from src.core.logger import setup_logging
from src.core.uow import UnitOfWork
from src.models import WebhookLog, get_utc_now
from src.schemas import (
    MetaWebhookPayload,
    WabaSyncRequest,
    WebhookEvent,
    WhatsAppMessage,
)
from src.services.campaign.sender import CampaignSenderService
from src.services.media.service import MediaService
from src.services.media.storage import AsyncIteratorFile, StorageService
from src.services.messaging.processor import MessageProcessorService
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService
from src.services.sync import SyncService
from taskiq import Context, TaskiqDepends

logger = setup_logging()
limiter = AsyncLimiter(10, 1)


async def get_http_client(context: Context = TaskiqDepends()) -> httpx.AsyncClient:
    return context.state.http_client


async def _get_meta_credentials() -> tuple[str | None, str]:
    """
    Допоміжна функція для отримання токена та базового URL з бази даних.
    Повертає (token, base_url).
    """
    token = None
    base_url = None

    try:
        async with UnitOfWork(async_session_maker) as uow:
            account = await uow.waba.get_credentials()
            if account:
                if account.access_token:
                    token = account.access_token

                if hasattr(account, "graph_api_version") and account.graph_api_version:
                    base_url = f"https://graph.facebook.com/{account.graph_api_version}"
    except Exception as e:
        logger.error(f"Failed to fetch WABA credentials: {e}")

    return token, base_url


@broker.task(
    task_name="handle_messages", retry_on_exception=True, max_retries=3, retry_delay=5
)
async def handle_messages_task(message: WhatsAppMessage):
    async with limiter:
        with logger.contextualize(request_id=message.request_id):
            token, base_url = await _get_meta_credentials()

            if not token:
                logger.error("Message sending aborted: No Access Token found in DB.")
                return

            async with httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            ) as client:
                uow = UnitOfWork(async_session_maker)
                meta_client = MetaClient(client, base_url=base_url)
                notifier = NotificationService()
                sender_service = MessageSenderService(uow, meta_client, notifier)

                await sender_service.send_manual_message(message)


@broker.task(
    task_name="handle_media_send",
    retry_on_exception=True,
    max_retries=3,
    retry_delay=5,
)
async def handle_media_send_task(
    phone_number: str,
    file_path: str,
    filename: str,
    mime_type: str,
    caption: str | None = None,
    request_id: str | None = None,
):
    async with limiter:
        with logger.contextualize(request_id=request_id or str(uuid.uuid4())):
            try:
                token, base_url = await _get_meta_credentials()

                if not token:
                    logger.error("Media sending aborted: No Access Token found.")
                    return

                async with httpx.AsyncClient(
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    timeout=60.0,
                ) as client:
                    uow = UnitOfWork(async_session_maker)
                    meta_client = MetaClient(client, base_url=base_url)
                    storage_service = StorageService()
                    notifier = NotificationService()

                    sender_service = MessageSenderService(
                        uow, meta_client, notifier, storage_service
                    )

                    if not os.path.exists(file_path):
                        logger.error(f"File not found at {file_path}")
                        return

                    async with aiofiles.open(file_path, "rb") as f:
                        file_bytes = await f.read()

                    await sender_service.send_media_message(
                        phone_number=phone_number,
                        file_bytes=file_bytes,
                        filename=filename,
                        mime_type=mime_type,
                        caption=caption,
                    )

                    logger.info(
                        f"Media message sent successfully to {phone_number}. File: {filename}"
                    )
            except Exception as e:
                logger.error(f"Error sending media: {e}")
                raise e
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)


@broker.task(task_name="sync_account_data")
async def handle_account_sync_task(message: WabaSyncRequest):
    with logger.contextualize(request_id=message.request_id):
        token, base_url = await _get_meta_credentials()

        if not token:
            logger.error("Sync aborted: No Access Token found in DB.")
            return

        async with httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        ) as client:
            uow = UnitOfWork(async_session_maker)
            meta_client = MetaClient(client, base_url=base_url)

            sync_service = SyncService(uow, meta_client)
            await sync_service.sync_account_data()


@broker.task(
    task_name="download_media", retry_on_exception=True, max_retries=3, retry_delay=5
)
async def handle_media_download_task(
    message_id: UUID,
    meta_media_id: str,
    media_type: str,
    mime_type: str,
    caption: str | None = None,
):
    with logger.contextualize(message_id=str(message_id), media_id=meta_media_id):
        token, base_url = await _get_meta_credentials()

        if not token:
            logger.error("Media download aborted: No Access Token found.")
            return

        async with httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
            },
            timeout=60.0,
        ) as client:
            uow = UnitOfWork(async_session_maker)
            meta_client = MetaClient(client, base_url=base_url)
            storage_service = StorageService()

            try:
                media_url = await meta_client.get_media_url(meta_media_id)

                ext = mimetypes.guess_extension(mime_type) or ".bin"
                filename = f"{uuid.uuid4()}{ext}"
                r2_key = f"whatsapp/{media_type}s/{filename}"

                logger.info(f"Starting stream download for {media_type}: {r2_key}")

                async with client.stream("GET", media_url) as response:
                    response.raise_for_status()
                    file_size = int(response.headers.get("content-length", 0))
                    file_stream = AsyncIteratorFile(response.aiter_bytes())

                    await storage_service.upload_stream(
                        file_stream=file_stream,
                        object_name=r2_key,
                        content_type=mime_type,
                    )

                async with uow:
                    await uow.messages.add_media_file(
                        message_id=message_id,
                        meta_media_id=meta_media_id,
                        file_name=filename,
                        file_mime_type=mime_type,
                        file_size=file_size,
                        caption=caption,
                        r2_key=r2_key,
                        bucket_name=settings.R2_BUCKET_NAME,
                    )
                    await uow.commit()

                logger.info(f"Media saved successfully: {r2_key}")

            except Exception as e:
                logger.error(f"Failed to process media: {e}")
                raise


@broker.task(
    task_name="raw_webhooks", retry_on_exception=True, max_retries=5, retry_delay=5
)
async def handle_raw_webhook_task(event: WebhookEvent):
    data = event.payload

    async with async_session_maker() as session:
        try:
            log_entry = WebhookLog(payload=data)
            session.add(log_entry)
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to save webhook log: {e}")

    token, base_url = await _get_meta_credentials()

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        uow = UnitOfWork(async_session_maker)
        meta_client = MetaClient(client, base_url=base_url)
        storage_service = StorageService()
        notifier = NotificationService()
        media_service = MediaService(uow, storage_service, meta_client)

        processor_service = MessageProcessorService(uow, media_service, notifier)

        webhook_payload = MetaWebhookPayload(**event.payload)
        await processor_service.process_webhook(webhook_payload)


@broker.task(task_name="process_campaign_batch")
async def process_campaign_batch_task(
    campaign_id: str,
    batch_number: int = 1,
):
    BATCH_SIZE = 100
    PROGRESS_UPDATE_INTERVAL = 10

    token, base_url = await _get_meta_credentials()
    if not token:
        logger.error(f"Campaign {campaign_id} batch processing aborted: No Token.")
        return

    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:
        uow = UnitOfWork(async_session_maker)
        meta_client = MetaClient(client, base_url=base_url)
        notifier = NotificationService()
        message_sender = MessageSenderService(uow, meta_client, notifier)
        sender = CampaignSenderService(uow, message_sender, notifier)

        async with uow:
            contacts = await uow.campaign_contacts.get_sendable_contacts(
                UUID(campaign_id), limit=BATCH_SIZE
            )

        if not contacts:
            await sender._check_campaign_completion(UUID(campaign_id))
            return

        batch_size = len(contacts)
        logger.info(f"Batch #{batch_number}: Processing {batch_size} contacts")

        await sender.notify_batch_progress(
            campaign_id=UUID(campaign_id),
            batch_number=batch_number,
            stats={
                "batch_size": batch_size,
                "processed": 0,
                "successful": 0,
                "failed": 0,
            },
        )

        processed = 0
        successful = 0
        failed = 0

        for link in contacts:
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

                if processed % PROGRESS_UPDATE_INTERVAL == 0 or processed == batch_size:
                    await sender.notify_batch_progress(
                        campaign_id=UUID(campaign_id),
                        batch_number=batch_number,
                        stats={
                            "batch_size": batch_size,
                            "processed": processed,
                            "successful": successful,
                            "failed": failed,
                        },
                    )

        logger.info(f"Batch #{batch_number} completed")
        await process_campaign_batch_task.kiq(campaign_id, batch_number + 1)


@broker.task(task_name="campaign_start")
async def handle_campaign_start_task(campaign_id: str):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            token, base_url = await _get_meta_credentials()
            if not token:
                raise ValueError("No Access Token found in DB")

            async with httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            ) as client:
                uow = UnitOfWork(async_session_maker)
                meta_client = MetaClient(client, base_url=base_url)
                notifier = NotificationService()
                message_sender = MessageSenderService(uow, meta_client, notifier)
                sender = CampaignSenderService(uow, message_sender, notifier)

                await sender.start_campaign(UUID(campaign_id))
                await process_campaign_batch_task.kiq(campaign_id, batch_number=1)

        except Exception as e:
            logger.exception(f"Campaign {campaign_id} failed to start")
            notifier = NotificationService()
            await notifier.notify_campaign_status(
                campaign_id=UUID(campaign_id), status="FAILED", error=str(e)
            )


@broker.task(task_name="campaign_resume")
async def handle_campaign_resume_task(campaign_id: str):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            token, base_url = await _get_meta_credentials()
            if not token:
                raise ValueError("No Access Token found in DB")

            async with httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            ) as client:
                uow = UnitOfWork(async_session_maker)
                meta_client = MetaClient(client, base_url=base_url)
                notifier = NotificationService()
                message_sender = MessageSenderService(uow, meta_client, notifier)
                sender = CampaignSenderService(uow, message_sender, notifier)

                await sender.resume_campaign(UUID(campaign_id))
                await process_campaign_batch_task.kiq(campaign_id)

        except Exception:
            logger.exception(f"Campaign {campaign_id} resume failed")


@broker.task(schedule=[{"cron": "* * * * *"}])
async def check_scheduled_campaigns_task():
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
