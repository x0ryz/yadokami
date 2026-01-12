from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

from .base import ContactStatus, get_utc_now
from .tags import ContactTagLink

if TYPE_CHECKING:
    from .campaigns import CampaignContact
    from .messages import Message
    from .tags import Tag


class Contact(SQLModel, table=True):
    __tablename__ = "contacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    phone_number: str = Field(unique=True, index=True)
    name: Optional[str] = None
    link: Optional[str] = None
    unread_count: int = Field(default=0)

    status: ContactStatus = Field(default=ContactStatus.ACTIVE)

    last_message_id: Optional[UUID] = Field(
        default=None, foreign_key="messages.id", nullable=True
    )

    last_message_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    source: Optional[str] = None
    tags: List["Tag"] = Relationship(
        back_populates="contacts", link_model=ContactTagLink
    )

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    last_message: Optional["Message"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "Contact.last_message_id",
            "post_update": True,
        }
    )

    messages: List["Message"] = Relationship(
        back_populates="contact",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Message.contact_id]",
        },
    )

    campaign_links: List["CampaignContact"] = Relationship(
        back_populates="contact",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
