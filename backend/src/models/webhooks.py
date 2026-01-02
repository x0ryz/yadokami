from datetime import datetime
from typing import Any, Dict
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, DateTime, Field, SQLModel

from .base import get_utc_now


class WebhookLog(SQLModel, table=True):
    __tablename__ = "webhook_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    processed_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
