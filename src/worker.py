import json

import httpx
from faststream import Context, ContextRepo, FastStream
from faststream.redis import RedisBroker
from redis import asyncio as aioredis

from src.clients.meta import MetaClient
from src.core.config import settings
from src.core.database import async_session_maker
from src.core.logger import setup_logging
from src.core.uow import UnitOfWork
from src.models import WebhookLog
from src.schemas import WabaSyncRequest, WebhookEvent, WhatsAppMessage
from src.services.sync import SyncService
from src.services.whatsapp import WhatsAppService

logger = setup_logging()

broker = RedisBroker(settings.REDIS_URL)
app = FastStream(broker)


@app.on_startup
async def setup_http_client(context: ContextRepo):
    client = httpx.AsyncClient(
        timeout=10.0,
        headers={
            "Authorization": f"Bearer {settings.META_TOKEN}",
            "Content-Type": "application/json",
        },
    )

    context.set_global("http_client", client)
    logger.info("HTTPX Client initialized")


@app.after_shutdown
async def close_http_client(context: ContextRepo):
    client = context.get("http_client")
    if client:
        await client.aclose()
        logger.info("HTTPX Client closed")


async def publish_ws_update(data: dict):
    try:
        # Використовуємо окреме з'єднання для гарантії "чистого" JSON
        redis = aioredis.from_url(settings.REDIS_URL)

        # Явно перетворюємо в JSON рядок
        message_json = json.dumps(data, default=str)

        await redis.publish("ws_updates", message_json)
        await redis.close()

        logger.info(f"WS EVENT PUBLISHED: {message_json}")
    except Exception as e:
        logger.error(f"Failed to publish WS update: {e}")


@broker.subscriber("whatsapp_messages")
async def handle_messages(
    message: WhatsAppMessage, client: httpx.AsyncClient = Context("http_client")
):
    with logger.contextualize(request_id=message.request_id):
        logger.info(f"Received message request for phone: {message.phone_number}")

        uow = UnitOfWork(async_session_maker)
        meta_client = MetaClient(client)
        service = WhatsAppService(uow, meta_client, notifier=publish_ws_update)

        await service.send_outbound_message(message)


@broker.subscriber("sync_account_data")
async def handle_account_sync(
    message: WabaSyncRequest, client: httpx.AsyncClient = Context("http_client")
):
    request_id = message.request_id

    with logger.contextualize(request_id=request_id):
        logger.info("Starting sync task...")

        async with async_session_maker() as session:
            meta_client = MetaClient(client)
            sync_service = SyncService(session, meta_client)

            await sync_service.sync_account_data()


@broker.subscriber("raw_webhooks")
async def handle_raw_webhook(
    event: WebhookEvent, client: httpx.AsyncClient = Context("http_client")
):
    data = event.payload

    # 1. Логування вебхука (тут можна залишити просту сесію, бо це окрема коротка дія)
    async with async_session_maker() as session:
        try:
            log_entry = WebhookLog(payload=data)
            session.add(log_entry)
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to save webhook log: {e}")

    # 2. Основна обробка
    try:
        # ✅ ВИПРАВЛЕННЯ: Створюємо UnitOfWork
        uow = UnitOfWork(async_session_maker)

        meta_client = MetaClient(client)

        # ✅ Передаємо uow, а не session
        service = WhatsAppService(uow, meta_client, notifier=publish_ws_update)

        await service.process_webhook(data)

    except Exception as e:
        logger.exception("Error processing webhook in service")
