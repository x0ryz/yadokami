from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.base import (
    CampaignStatus,
    TimestampMixin,
    UUIDMixin,
)

if TYPE_CHECKING:
    from src.models.contacts import Contact
    from src.models.messages import Message
    from src.models.templates import Template
    from src.models.waba import WabaPhoneNumber


class Campaign(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String)
    status: Mapped[CampaignStatus] = mapped_column(
        default=CampaignStatus.DRAFT, index=True
    )

    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )
    waba_phone_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("waba_phone_numbers.id"), nullable=True
    )

    variable_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # timing
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    template: Mapped["Template | None"] = relationship(back_populates="campaigns")
    waba_phone: Mapped["WabaPhoneNumber | None"] = relationship()
    contacts: Mapped[list["CampaignContact"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignContact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "campaign_contacts"

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), index=True)

    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )

    retry_count: Mapped[int] = mapped_column(default=0)

    campaign: Mapped["Campaign"] = relationship(back_populates="contacts")
    contact: Mapped["Contact"] = relationship(back_populates="campaign_links")
    message: Mapped["Message | None"] = relationship()
