from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthComponent(BaseModel):
    status: Literal["up", "down", "degraded"]
    latency_ms: float
    details: str | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy", "degraded"]
    version: str
    uptime_seconds: float
    timestamp: str
    components: dict[str, HealthComponent]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "uptime_seconds": 3600.5,
                "timestamp": "2024-01-25T12:00:00Z",
                "components": {
                    "database": {"status": "up", "latency_ms": 15.2},
                    "broker": {"status": "up", "latency_ms": 5.1},
                },
            }
        }
    )
