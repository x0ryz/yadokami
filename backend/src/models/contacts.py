from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

from .base import ContactStatus, get_utc_now

if TYPE_CHECKING:
    from .campaigns import CampaignContact
    from .messages import Message


class Contact(SQLModel, table=True):
    __tablename__ = "contacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    phone_number: str = Field(unique=True, index=True)
    name: Optional[str] = None
    unread_count: int = Field(default=0)

    status: ContactStatus = Field(default=ContactStatus.NEW)
    last_message_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    source: Optional[str] = None
    tags: List[str] = Field(default=[], sa_column=Column(JSONB))

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    messages: List["Message"] = Relationship(back_populates="contact")
    campaign_links: List["CampaignContact"] = Relationship(back_populates="contact")
