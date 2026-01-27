from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field, computed_field

from src.models.base import CampaignStatus, MessageStatus

from .base import TimestampMixin, UUIDMixin


class CampaignCreate(BaseModel):
    """Campaign creation schema"""

    name: str = Field(..., min_length=1, max_length=255)
    template_id: UUID | None = None
    waba_phone_id: UUID | None = None
    variable_mapping: dict[str, str] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Black Friday Campaign",
                "message_type": "template",
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
    )


class CampaignUpdate(BaseModel):
    """Campaign update schema"""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    template_id: UUID | None = None
    variable_mapping: dict[str, str] | None = None


class CampaignSchedule(BaseModel):
    """Campaign planning schema"""

    scheduled_at: datetime = Field(
        ..., description="ISO 8601 datetime when to start the campaign"
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"scheduled_at": "2024-12-31T12:00:00Z"}}
    )


class CampaignResponse(UUIDMixin, TimestampMixin):
    name: str
    status: CampaignStatus
    template_id: UUID | None = None
    waba_phone_id: UUID | None = None
    variable_mapping: dict[str, str] | None = None

    # Інформація про дати
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CampaignStatsResponse(CampaignResponse):
    total_contacts: int
    sent_count: int
    delivered_count: int
    read_count: int = 0
    replied_count: int = 0
    failed_count: int

    @computed_field
    def progress_percent(self) -> float:
        if self.total_contacts == 0:
            return 0.0
        processed = self.delivered_count + self.failed_count
        return round((processed / self.total_contacts) * 100, 2)


class CampaignListResponse(UUIDMixin, TimestampMixin):
    name: str
    status: CampaignStatus
    scheduled_at: datetime | None = None
    template_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CampaignContactResponse(BaseModel):
    id: UUID
    contact_id: UUID
    phone_number: str = Field(validation_alias=AliasPath("contact", "phone_number"))
    name: str | None = Field(
        default=None, validation_alias=AliasPath("contact", "name")
    )
    custom_data: dict[str, Any] = Field(
        default_factory=dict, validation_alias=AliasPath("contact", "custom_data")
    )
    retry_count: int

    message: Any | None = Field(default=None, exclude=True)

    @computed_field
    def status(self) -> str:
        msg = getattr(self, "message", None)
        if msg and msg.status:
            if hasattr(msg.status, "value"):
                return str(msg.status.value)
            return str(msg.status)
        return "queued"

    @computed_field
    def error_code(self) -> int | None:
        if self.message:
            return self.message.error_code
        return None

    @computed_field
    def error_message(self) -> str | None:
        if self.message:
            return self.message.error_message
        return None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CampaignContactUpdate(BaseModel):
    """Campaign contact update schema"""

    name: str | None = None
    custom_data: dict[str, Any] | None = None
    status: MessageStatus | None = None


class CampaignStartResponse(BaseModel):
    """Response to campaign launch request"""

    status: str = "started"
    campaign_id: UUID
    message: str = "Campaign started successfully"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "started",
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Campaign started successfully",
            }
        }
    )
