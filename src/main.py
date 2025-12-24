import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from redis import asyncio as aioredis

from src.core.config import settings
from src.core.database import engine
from src.core.logger import setup_logging
from src.core.websocket import redis_listener
from src.routes import contacts, messages, waba, webhooks

background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan: Starting up...")

    redis = aioredis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )

    app.state.redis = redis
    logger.info("Redis pool initialized")

    task = asyncio.create_task(redis_listener())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    yield

    logger.info("Lifespan: Shutting down...")

    for task in background_tasks:
        task.cancel()

    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

    await app.state.redis.close()
    logger.info("Redis client closed")

    await engine.dispose()
    logger.info("Database engine disposed")


logger = setup_logging()
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(contacts.router)
app.include_router(messages.router)
app.include_router(waba.router)

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[
        ".*admin.*",
        "/metrics",
    ],
    env_var_name="ENABLE_METRICS",
    inprogress_name="inprogress",
    inprogress_labels=True,
)

instrumentator.instrument(app).expose(app)
