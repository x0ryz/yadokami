from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, table


def get_utc_now():
    return datetime.now(timezone.utc)


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RECEIVED = "received"


class ContactStatus(str, Enum):
    NEW = "new"
    SCHEDULED = "scheduled"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    OPTED_OUT = "opted_out"
    BLOCKED = "blocked"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Template(SQLModel, table=True):
    """WhatsApp Message Templates synced from Meta"""

    __tablename__ = "templates"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    waba_id: UUID = Field(foreign_key="waba_accounts.id")
    waba: Optional["WabaAccount"] = Relationship(back_populates="templates")

    meta_template_id: str = Field(index=True, unique=True)
    name: str = Field(index=True)
    language: str
    status: str
    category: str

    components: list[Dict[str, Any]] = Field(default=[], sa_column=Column(JSONB))

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    campaigns: list["Campaign"] = Relationship(back_populates="template")


class WabaAccount(SQLModel, table=True):
    """Business account (phone number connected to WABA)"""

    __tablename__ = "waba_accounts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    waba_id: str
    name: str
    account_review_status: Optional[str] = None
    business_verification_status: Optional[str] = None

    templates: list["Template"] = Relationship(back_populates="waba")
    phone_numbers: list["WabaPhoneNumber"] = Relationship(back_populates="waba")


class WabaPhoneNumber(SQLModel, table=True):
    """Phone numbers associated with WABA accounts"""

    __tablename__ = "waba_phone_numbers"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    waba_id: UUID = Field(foreign_key="waba_accounts.id")
    waba: Optional[WabaAccount] = Relationship(back_populates="phone_numbers")

    phone_number_id: str = Field(unique=True, index=True)
    display_phone_number: str

    status: Optional[str] = None

    quality_rating: str = Field(default="UNKNOWN")
    messaging_limit_tier: Optional[str] = None

    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    messages: list["Message"] = Relationship(back_populates="waba_phone")


class Contact(SQLModel, table=True):
    """Contacts stored in the system"""

    __tablename__ = "contacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    phone_number: str = Field(unique=True, index=True)
    name: Optional[str] = None

    unread_count: int = Field(default=0)

    # Campaign tracking
    status: ContactStatus = Field(default=ContactStatus.NEW)

    # 24-hour window tracking
    last_message_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # Metadata
    source: Optional[str] = None  # "import_csv", "manual", "webhook"
    tags: List[str] = Field(default=[], sa_column=Column(JSONB))

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    messages: list["Message"] = Relationship(back_populates="contact")
    campaign_links: list["CampaignContact"] = Relationship(back_populates="contact")


class Campaign(SQLModel, table=True):
    """Campaign for mass messaging"""

    __tablename__ = "campaigns"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    status: CampaignStatus = Field(default=CampaignStatus.DRAFT, index=True)

    # Message configuration
    message_type: str = Field(default="template")  # "text" or "template"
    template_id: Optional[UUID] = Field(default=None, foreign_key="templates.id")
    message_body: Optional[str] = None

    # Scheduling
    scheduled_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # Statistics
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

    # Relationships
    template: Optional[Template] = Relationship(back_populates="campaigns")
    contacts: list["CampaignContact"] = Relationship(
        back_populates="campaign",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class CampaignContact(SQLModel, table=True):
    """Link between campaigns and contacts"""

    __tablename__ = "campaign_contacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    campaign_id: UUID = Field(foreign_key="campaigns.id", index=True)
    contact_id: UUID = Field(foreign_key="contacts.id", index=True)

    status: ContactStatus = Field(default=ContactStatus.NEW, index=True)
    message_id: Optional[UUID] = Field(default=None, foreign_key="messages.id")

    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    # Relationships
    campaign: Optional[Campaign] = Relationship(back_populates="contacts")
    contact: Optional[Contact] = Relationship(back_populates="campaign_links")
    message: Optional["Message"] = Relationship()


class MediaFile(SQLModel, table=True):
    __tablename__ = "media_files"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    message_id: Optional[UUID] = Field(default=None, foreign_key="messages.id")

    meta_media_id: str = Field(index=True)

    file_name: str
    file_mime_type: str
    file_size: Optional[int] = None

    caption: Optional[str] = Field(default=None)

    r2_key: str
    bucket_name: str

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    message: Optional["Message"] = Relationship(back_populates="media_files")


class Message(SQLModel, table=True):
    """Messages sent and received via WhatsApp"""

    __tablename__ = "messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    wamid: Optional[str] = Field(default=None, index=True)

    waba_phone_id: UUID = Field(foreign_key="waba_phone_numbers.id")
    contact_id: UUID = Field(foreign_key="contacts.id")

    direction: MessageDirection
    status: MessageStatus = Field(default=MessageStatus.PENDING)

    message_type: str = Field(default="text")
    body: Optional[str] = Field(default=None)

    template_id: Optional[UUID] = Field(default=None, foreign_key="templates.id")

    media_files: list["MediaFile"] = Relationship(back_populates="message")

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    contact: Optional[Contact] = Relationship(back_populates="messages")
    waba_phone: Optional[WabaPhoneNumber] = Relationship(back_populates="messages")


class WebhookLog(SQLModel, table=True):
    """Log for all incoming webhooks processed via Redis"""

    __tablename__ = "webhook_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    processed_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
