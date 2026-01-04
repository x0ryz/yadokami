import httpx
from src.core.config import settings
from src.core.logger import setup_logging
from src.core.redis import close_redis, init_redis
from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend, RedisScheduleSource

logger = setup_logging()

result_backend = RedisAsyncResultBackend(
    redis_url=settings.REDIS_URL,
)

broker = ListQueueBroker(
    url=settings.REDIS_URL,
    queue_name="jidoka_tasks",
).with_result_backend(result_backend)

redis_source = RedisScheduleSource(settings.REDIS_URL)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        LabelScheduleSource(broker),
        redis_source,
    ],
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState):
    client = httpx.AsyncClient(
        timeout=10.0,
        headers={
            "Authorization": f"Bearer {settings.META_TOKEN}",
            "Content-Type": "application/json",
        },
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
