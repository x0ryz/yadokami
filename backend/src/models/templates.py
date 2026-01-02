from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

from .base import get_utc_now

if TYPE_CHECKING:
    from .campaigns import Campaign
    from .waba import WabaAccount


class Template(SQLModel, table=True):
    __tablename__ = "templates"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    waba_id: UUID = Field(foreign_key="waba_accounts.id")
    waba: Optional["WabaAccount"] = Relationship(back_populates="templates")

    meta_template_id: str = Field(index=True, unique=True)
    name: str = Field(index=True)
    language: str
    status: str
    category: str

    components: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSONB))

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    campaigns: List["Campaign"] = Relationship(back_populates="template")
