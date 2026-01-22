from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.base import ContactStatus, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.campaigns import CampaignContact
    from src.models.messages import Message
    from src.models.tags import Tag


class Contact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contacts"

    phone_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    unread_count: Mapped[int] = mapped_column(default=0)

    status: Mapped[ContactStatus] = mapped_column(default=ContactStatus.ACTIVE)

    last_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", use_alter=True, name="fk_contacts_last_message_id"),
        nullable=True,
    )

    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_incoming_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    source: Mapped[str | None] = mapped_column(String, nullable=True)

    # properties

    @property
    def is_session_open(self) -> bool:
        if not self.last_incoming_message_at:
            return False

        current_time = datetime.now(timezone.utc)
        expiration_time = self.last_incoming_message_at + timedelta(hours=24)

        return current_time < expiration_time

    # relationships

    tags: Mapped[list["Tag"]] = relationship(
        secondary="contact_tags", back_populates="contacts"
    )

    last_message: Mapped["Message | None"] = relationship(
        foreign_keys=[last_message_id], post_update=True
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="contact",
        cascade="all, delete-orphan",
        foreign_keys="[Message.contact_id]",
    )

    campaign_links: Mapped[list["CampaignContact"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
