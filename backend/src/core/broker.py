import httpx
from src.core.config import settings
from src.core.database import async_session_maker
from src.core.logger import setup_logging
from src.core.redis import close_redis, init_redis
from src.core.uow import UnitOfWork
from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import (
    ListQueueBroker,
    ListRedisScheduleSource,
    RedisAsyncResultBackend,
)

logger = setup_logging()

result_backend = RedisAsyncResultBackend(
    redis_url=settings.REDIS_URL,
)

broker = ListQueueBroker(
    url=settings.REDIS_URL,
    queue_name="jidoka_tasks",
).with_result_backend(result_backend)

redis_source = ListRedisScheduleSource(settings.REDIS_URL)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        LabelScheduleSource(broker),
        redis_source,
    ],
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState):
    token = None

    async with UnitOfWork(async_session_maker) as uow:
        try:
            account = await uow.waba.get_credentials()
            if account and account.access_token:
                token = account.access_token
                logger.info("Taskiq Worker: Using Meta Token from Database.")
            else:
                logger.warning("Taskiq Worker: WABA Account or Token not found in DB.")
        except Exception as e:
            logger.error(f"Taskiq Worker: Failed to fetch token from DB. Error: {e}")

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.critical("Taskiq Worker: Starting WITHOUT Authorization token!")

    client = httpx.AsyncClient(
        timeout=10.0,
        headers=headers,
    )
    state.http_client = client

    await init_redis()

    logger.info("Taskiq Worker started. HTTP Client initialized.")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState):
    client = getattr(state, "http_client", None)
    if client:
        await client.aclose()

    await close_redis()

    logger.info("Taskiq Worker stopped.")
