import asyncio

import httpx
import sentry_sdk
from faststream import ContextRepo, FastStream

from src.core.broker import broker, setup_jetstream
from src.core.config import settings
from src.worker.dependencies import logger
from src.worker.routers.campaigns import router as campaigns_router
from src.worker.routers.media import router as media_router
from src.worker.routers.messages import router as messages_router
from src.worker.routers.system import router as system_router
from src.worker.tasks import scheduled_campaigns_checker, scheduled_messages_checker

app = FastStream(broker)

broker.include_router(campaigns_router)
broker.include_router(messages_router)
broker.include_router(media_router)
broker.include_router(system_router)

campaign_scheduler_task: asyncio.Task | None = None
message_scheduler_task: asyncio.Task | None = None

if settings.SENTRY_WORKER_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_WORKER_DSN,
        send_default_pii=True,
    )


@app.on_startup
async def startup_handler(context: ContextRepo):
    global campaign_scheduler_task, message_scheduler_task
    logger.info("FastStream Worker: Starting up...")

    http_client = httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
    )
    context.set_global("http_client", http_client)

    await setup_jetstream()

    campaign_scheduler_task = asyncio.create_task(
        scheduled_campaigns_checker(broker))
    message_scheduler_task = asyncio.create_task(
        scheduled_messages_checker(broker))
    logger.info("Startup complete.")


@app.on_shutdown
async def shutdown_handler(context: ContextRepo):
    global campaign_scheduler_task, message_scheduler_task
    logger.info("FastStream Worker: Shutting down...")

    tasks = []
    if campaign_scheduler_task:
        tasks.append(campaign_scheduler_task)
    if message_scheduler_task:
        tasks.append(message_scheduler_task)

    for task in tasks:
        task.cancel()

    if tasks:
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    http_client = context.get("http_client")
    if http_client:
        await http_client.aclose()
    logger.info("Shutdown complete.")

