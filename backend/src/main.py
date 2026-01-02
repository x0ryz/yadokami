import asyncio
from contextlib import asynccontextmanager

import sentry_sdk
import taskiq_fastapi
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import asyncio as aioredis
from src.core.broker import broker
from src.core.config import settings
from src.core.database import engine
from src.core.logger import setup_logging
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

background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan: Starting up...")

    redis = aioredis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )

    app.state.redis = redis
    logger.info("Redis pool initialized")

    ws_task = asyncio.create_task(redis_listener())
    background_tasks.add(ws_task)
    ws_task.add_done_callback(background_tasks.discard)

    if not broker.is_worker_process:
        await broker.startup()

    yield

    logger.info("Lifespan: Shutting down...")

    for task in background_tasks:
        task.cancel()

    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

    if not broker.is_worker_process:
        await broker.shutdown()

    await app.state.redis.close()
    logger.info("Redis client closed")

    await engine.dispose()
    logger.info("Database engine disposed")


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        send_default_pii=True,
        enable_logs=True,
    )


logger = setup_logging()
app = FastAPI(lifespan=lifespan)

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
