import asyncio
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI

from src.core.broker import broker
from src.core.database import engine
from src.core.logger import setup_logging
from src.core.redis import close_redis, init_redis, redis_client
from src.core.websocket import redis_listener

logger = setup_logging()

# Module-level set to track background tasks
background_tasks: Set[asyncio.Task] = set()


# Startup functions


async def initialize_redis(app: FastAPI) -> None:
    """Initialize Redis connection and attach to app state."""
    await init_redis()
    app.state.redis = redis_client
    logger.info("Redis pool initialized")


async def start_websocket_listener() -> None:
    """Start the WebSocket listener as a background task."""
    ws_task = asyncio.create_task(redis_listener())
    background_tasks.add(ws_task)
    ws_task.add_done_callback(background_tasks.discard)
    logger.info("WebSocket listener started")


async def initialize_broker() -> None:
    """Initialize the task broker if not in worker process."""
    if not broker.is_worker_process:
        await broker.startup()
        logger.info("Broker started")


# Shutdown functions


async def shutdown_background_tasks() -> None:
    """Cancel and cleanup all background tasks."""
    for task in background_tasks:
        task.cancel()

    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

    logger.info("Background tasks shutdown complete")


async def shutdown_broker() -> None:
    """Shutdown the task broker if not in worker process."""
    if not broker.is_worker_process:
        await broker.shutdown()
        logger.info("Broker shutdown")


async def shutdown_redis() -> None:
    """Close Redis connection."""
    await close_redis()
    logger.info("Redis client closed")


async def shutdown_database() -> None:
    """Dispose database engine."""
    await engine.dispose()
    logger.info("Database engine disposed")


# Main lifespan context manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""
    logger.info("Lifespan: Starting up...")

    # Startup sequence
    await initialize_redis(app)
    await start_websocket_listener()
    await initialize_broker()

    yield

    # Shutdown sequence
    logger.info("Lifespan: Shutting down...")
    await shutdown_background_tasks()
    await shutdown_broker()
    await shutdown_redis()
    await shutdown_database()
