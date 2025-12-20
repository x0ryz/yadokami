from sqlmodel import SQLModel, Field, Relationship, Column, DateTime
from typing import Optional
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime, timezone


def get_utc_now():
    return datetime.now(timezone.utc)


class WabaAccount(SQLModel, table=True):
    """Business account (phone number connected to WABA)"""

    __tablename__ = "waba_accounts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    waba_id: str
    name: str
    account_review_status: Optional[str] = None
    business_verification_status: Optional[str] = None

    phone_numbers: list["WabaPhoneNumber"] = Relationship(
        back_populates="waba")


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
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True))
    )

    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True))
    )
