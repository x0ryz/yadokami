import asyncio
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
import taskiq_fastapi
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.broker import broker
from src.core.config import settings
from src.core.database import engine
from src.core.exceptions import BaseException
from src.core.handlers import global_exception_handler, local_exception_handler
from src.core.logger import setup_logging
from src.core.redis import close_redis, init_redis, redis_client
from src.core.websocket import redis_listener
from src.routes import (
    campaigns,
    contacts,
    dashboard,
    messages,
    templates,
    waba,
    webhooks,
)
from src.schemas.waba import WabaSyncRequest
from src.worker import handle_account_sync_task

background_tasks = set()

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan: Starting up...")

    await init_redis()

    app.state.redis = redis_client
    logger.info("Redis pool initialized")

    ws_task = asyncio.create_task(redis_listener())
    background_tasks.add(ws_task)
    ws_task.add_done_callback(background_tasks.discard)

    if not broker.is_worker_process:
        await broker.startup()

        try:
            request_id = str(uuid.uuid4())
            logger.info(f"Auto-triggering WABA sync on startup. ID: {request_id}")

            sync_request = WabaSyncRequest(request_id=request_id)
            await handle_account_sync_task.kiq(sync_request)

        except Exception as e:
            logger.error(f"Failed to auto-trigger WABA sync: {e}")

    yield

    logger.info("Lifespan: Shutting down...")

    for task in background_tasks:
        task.cancel()

    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

    if not broker.is_worker_process:
        await broker.shutdown()

    await close_redis()
    logger.info("Redis client closed")

    await engine.dispose()
    logger.info("Database engine disposed")


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        send_default_pii=True,
        enable_logs=True,
    )

app = FastAPI(lifespan=lifespan)

app.add_exception_handler(BaseException, local_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

taskiq_fastapi.init(broker, app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(contacts.router)
app.include_router(messages.router)
app.include_router(waba.router)
app.include_router(campaigns.router)
app.include_router(templates.router)
app.include_router(dashboard.router)
