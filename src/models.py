from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
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


class WabaAccount(SQLModel, table=True):
    """Business account (phone number connected to WABA)"""

    __tablename__ = "waba_accounts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    waba_id: str
    name: str
    account_review_status: Optional[str] = None
    business_verification_status: Optional[str] = None

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
    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    messages: list["Message"] = Relationship(back_populates="contact")


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
