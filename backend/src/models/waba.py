from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel

from .base import get_utc_now

if TYPE_CHECKING:
    from .messages import Message
    from .templates import Template


class WabaAccount(SQLModel, table=True):
    __tablename__ = "waba_accounts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    waba_id: str
    name: str
    account_review_status: Optional[str] = None
    business_verification_status: Optional[str] = None

    # Використовуємо строки для уникнення циклічних імпортів
    templates: List["Template"] = Relationship(back_populates="waba")
    phone_numbers: List["WabaPhoneNumber"] = Relationship(back_populates="waba")


class WabaPhoneNumber(SQLModel, table=True):
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

    messages: List["Message"] = Relationship(back_populates="waba_phone")
