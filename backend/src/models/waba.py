from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base, EncryptedString
from src.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.messages import Message
    from src.models.templates import Template


class WabaAccount(Base, UUIDMixin):
    __tablename__ = "waba_accounts"

    waba_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)

    access_token: Mapped[str] = mapped_column(EncryptedString)
    app_secret: Mapped[str] = mapped_column(EncryptedString)
    verify_token: Mapped[str] = mapped_column(EncryptedString)

    graph_api_version: Mapped[str] = mapped_column(String, default="v21.0")
    account_review_status: Mapped[str | None] = mapped_column(String, nullable=True)
    business_verification_status: Mapped[str | None] = mapped_column(
        String, nullable=True
    )

    templates: Mapped[list["Template"]] = relationship(back_populates="waba")
    phone_numbers: Mapped[list["WabaPhoneNumber"]] = relationship(back_populates="waba")


class WabaPhoneNumber(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "waba_phone_numbers"

    waba_id: Mapped[UUID] = mapped_column(ForeignKey("waba_accounts.id"))
    waba: Mapped["WabaAccount | None"] = relationship(back_populates="phone_numbers")

    phone_number_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_phone_number: Mapped[str] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_rating: Mapped[str] = mapped_column(String, default="UNKNOWN")
    messaging_limit_tier: Mapped[str | None] = mapped_column(String, nullable=True)

    messages: Mapped[list["Message"]] = relationship(back_populates="waba_phone")
