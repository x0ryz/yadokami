import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI
from src.core.broker import broker
from src.core.config import settings
from src.core.database import engine
from src.core.logger import setup_logging
from src.core.redis import close_redis, init_redis, redis_client
from src.core.websocket import redis_listener
from src.models import WabaAccount
from src.schemas.waba import WabaSyncRequest
from src.worker import handle_account_sync_task

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


async def trigger_waba_sync() -> None:
    """Trigger initial WABA sync on startup."""
    if broker.is_worker_process:
        return

    try:
        request_id = str(uuid.uuid4())
        logger.info(f"Auto-triggering WABA sync on startup. ID: {request_id}")

        sync_request = WabaSyncRequest(request_id=request_id)
        await handle_account_sync_task.kiq(sync_request)

    except Exception as e:
        logger.error(f"Failed to auto-trigger WABA sync: {e}")


async def initialize_waba_account() -> None:
    """Initialize WABA account from environment variables on startup."""
    if broker.is_worker_process:
        return

    try:
        from src.core.database import async_session_maker
        from src.core.uow import UnitOfWork

        async with UnitOfWork(async_session_maker) as uow:
            # Check if account already exists
            account = await uow.waba.get_account()

            if account and account.waba_id == settings.WABA_ID:
                # Account exists with correct ID, no need to update
                logger.info(
                    f"WABA account already initialized: {account.waba_id}"
                )
                return

            # Create or update account from env variables
            if account:
                # Update existing account with new values
                account.waba_id = settings.WABA_ID
                account.name = settings.WABA_NAME
                uow.waba.add(account)
                logger.info(
                    f"Updated WABA account from environment: {settings.WABA_ID}"
                )
            else:
                # Create new account from env variables
                account = WabaAccount(
                    waba_id=settings.WABA_ID, name=settings.WABA_NAME
                )
                uow.waba.add(account)
                logger.info(
                    f"Initialized WABA account from environment: {settings.WABA_ID}"
                )

            await uow.commit()

    except Exception as e:
        logger.error(f"Failed to initialize WABA account from env: {e}")


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
    await initialize_waba_account()
    await trigger_waba_sync()

    yield

    # Shutdown sequence
    logger.info("Lifespan: Shutting down...")
    await shutdown_background_tasks()
    await shutdown_broker()
    await shutdown_redis()
    await shutdown_database()
