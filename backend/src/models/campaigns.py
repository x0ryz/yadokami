from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

from .base import CampaignDeliveryStatus, CampaignStatus, get_utc_now

if TYPE_CHECKING:
    from .contacts import Contact
    from .messages import Message
    from .templates import Template


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    status: CampaignStatus = Field(default=CampaignStatus.DRAFT, index=True)

    message_type: str = Field(default="template")
    template_id: Optional[UUID] = Field(default=None, foreign_key="templates.id")
    message_body: Optional[str] = None

    scheduled_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    total_contacts: int = Field(default=0)
    sent_count: int = Field(default=0)
    delivered_count: int = Field(default=0)
    failed_count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    template: Optional["Template"] = Relationship(back_populates="campaigns")
    contacts: List["CampaignContact"] = Relationship(
        back_populates="campaign",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class CampaignContact(SQLModel, table=True):
    __tablename__ = "campaign_contacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    campaign_id: UUID = Field(foreign_key="campaigns.id", index=True)
    contact_id: UUID = Field(foreign_key="contacts.id", index=True)

    status: CampaignDeliveryStatus = Field(
        default=CampaignDeliveryStatus.QUEUED, index=True
    )
    message_id: Optional[UUID] = Field(default=None, foreign_key="messages.id")

    error_message: Optional[str] = None
    retry_count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    campaign: Optional[Campaign] = Relationship(back_populates="contacts")
    contact: Optional["Contact"] = Relationship(back_populates="campaign_links")
    message: Optional["Message"] = Relationship()
