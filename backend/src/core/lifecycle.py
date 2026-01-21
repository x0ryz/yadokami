import asyncio
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI

from src.core.broker import broker, setup_jetstream
from src.core.database import engine
from src.core.logger import setup_logging
from src.core.websocket import nats_listener

logger = setup_logging()

background_tasks: Set[asyncio.Task] = set()


async def start_websocket_listener() -> None:
    """Start the WebSocket listener as a background task."""
    ws_task = asyncio.create_task(nats_listener())
    background_tasks.add(ws_task)
    ws_task.add_done_callback(background_tasks.discard)
    logger.info("WebSocket listener started")


async def initialize_broker() -> None:
    """Initialize the NATS broker for publishing (not worker mode)."""
    await broker.connect()
    logger.info("NATS broker connected for publishing")

    # Setup JetStream streams and KV buckets
    await setup_jetstream()
    logger.info("JetStream setup completed")


async def shutdown_background_tasks() -> None:
    """Cancel and cleanup all background tasks."""
    for task in background_tasks:
        task.cancel()

    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

    logger.info("Background tasks shutdown complete")


async def shutdown_broker() -> None:
    """Shutdown the NATS broker connection."""
    await broker.stop()
    logger.info("NATS broker disconnected")


async def shutdown_database() -> None:
    """Dispose database engine."""
    await engine.dispose()
    logger.info("Database engine disposed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""
    logger.info("Lifespan: Starting up...")

    await start_websocket_listener()
    await initialize_broker()

    yield

    logger.info("Lifespan: Shutting down...")
    await shutdown_background_tasks()
    await shutdown_broker()
    await shutdown_database()
