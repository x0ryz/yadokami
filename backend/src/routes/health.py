import asyncio
import time
from datetime import datetime

from fastapi import APIRouter, Response, status
from loguru import logger
from sqlalchemy import text

from src.core.broker import broker
from src.core.database import async_session_maker
from src.models.base import get_utc_now
from src.schemas.health import HealthComponent, HealthResponse

router = APIRouter(tags=["Health"])

# Зберігаємо час запуску процесу
START_TIME = time.time()
VERSION = "1.0.0"


async def check_database() -> HealthComponent:
    """Перевірка підключення до PostgreSQL."""
    t0 = time.time()
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.time() - t0) * 1000
        return HealthComponent(status="up", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.time() - t0) * 1000
        logger.error(f"Health check failed for Database: {e}")
        return HealthComponent(
            status="down",
            latency_ms=round(latency, 2),
            details=str(e)
        )


async def check_broker() -> HealthComponent:
    """Перевірка підключення до NATS шліхом спроби публікації."""
    t0 = time.time()
    # logger.info(f"Checking broker health... ID={id(broker)}")
    try:
        # Ми намагаємось опублікувати порожнє повідомлення в топік health.check
        # Якщо брокер не підключений, faststream викине помилку (під капотом)
        await broker.publish(
            message={"ping": "pong"},
            subject="health.check"
        )
        
        latency = (time.time() - t0) * 1000
        return HealthComponent(
            status="up", 
            latency_ms=round(latency, 2),
            details=None
        )
    except Exception as e:
        latency = (time.time() - t0) * 1000
        # logger.error(f"Health check failed for Broker: {e}") 
        
        # Diagnostics
        connected_prop = getattr(broker, "connected", "Unknown")
        error_type = type(e).__name__
        
        return HealthComponent(
            status="down",
            latency_ms=round(latency, 2),
            details=f"Publish failed: {error_type}: {str(e)} | broker.connected={connected_prop}"
        )


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """
    Liveness probe.
    Використовується оркестратором (Docker/K8s) щоб знати чи процес живий.
    Не перевіряє залежності (щоб не перезавантажувати сервіс якщо впала база).
    """
    return {"status": "alive", "uptime": round(time.time() - START_TIME, 2)}


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_probe(response: Response):
    """
    Readiness probe.
    Використовується балансувальником навантаження.
    Перевіряє чи сервіс МИТТЄВО готовий обробити запит (чи є зв'язок з БД та іншим).
    """
    # Паралельна перевірка всіх компонентів
    db_status, broker_status = await asyncio.gather(
        check_database(),
        check_broker()
    )

    components = {
        "database": db_status,
        "broker": broker_status,
    }

    # Визначаємо загальний статус
    is_healthy = all(c.status == "up" for c in components.values())
    
    # Якщо хоча б один компонент лежить - повертаємо 503
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "unhealthy"
    else:
        response.status_code = status.HTTP_200_OK
        overall_status = "healthy"

    return HealthResponse(
        status=overall_status,
        version=VERSION,
        uptime_seconds=round(time.time() - START_TIME, 2),
        timestamp=get_utc_now().isoformat(),
        components=components
    )
