from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.base import (
    MessageDirection,
    MessageStatus,
    TimestampMixin,
    UUIDMixin,
    get_utc_now,
)

if TYPE_CHECKING:
    from src.models.contacts import Contact
    from src.models.waba import WabaPhoneNumber


class MediaFile(Base, UUIDMixin):
    __tablename__ = "media_files"

    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )

    meta_media_id: Mapped[str] = mapped_column(String, index=True)
    file_name: Mapped[str] = mapped_column(String)
    file_mime_type: Mapped[str] = mapped_column(String)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    caption: Mapped[str | None] = mapped_column(String, nullable=True)

    r2_key: Mapped[str] = mapped_column(String)
    bucket_name: Mapped[str] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=get_utc_now
    )

    message: Mapped["Message | None"] = relationship(
        back_populates="media_files")


class Message(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "messages"

    wamid: Mapped[str | None] = mapped_column(
        String, index=True, nullable=True)

    waba_phone_id: Mapped[UUID] = mapped_column(
        ForeignKey("waba_phone_numbers.id"))
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"))

    direction: Mapped[MessageDirection]
    status: Mapped[MessageStatus] = mapped_column(
        default=MessageStatus.PENDING)

    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    message_type: Mapped[str] = mapped_column(String, default="text")
    body: Mapped[str | None] = mapped_column(String, nullable=True)

    reply_to_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )
    reaction: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Scheduled message support
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )

    media_files: Mapped[list["MediaFile"]] = relationship(
        back_populates="message")

    contact: Mapped["Contact | None"] = relationship(
        back_populates="messages", foreign_keys=[contact_id]
    )
    waba_phone: Mapped["WabaPhoneNumber | None"] = relationship(
        back_populates="messages"
    )

    parent_message: Mapped["Message | None"] = relationship(
        remote_side="Message.id")
