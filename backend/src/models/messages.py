from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

from .base import MessageDirection, MessageStatus, get_utc_now

if TYPE_CHECKING:
    from .contacts import Contact
    from .templates import Template
    from .waba import WabaPhoneNumber


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

    media_files: List[MediaFile] = Relationship(back_populates="message")

    created_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True))
    )

    contact: Optional["Contact"] = Relationship(back_populates="messages")
    waba_phone: Optional["WabaPhoneNumber"] = Relationship(back_populates="messages")
