from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, Field, computed_field

from src.models.base import CampaignDeliveryStatus, CampaignStatus

from .base import TimestampMixin, UUIDMixin


class CampaignCreate(BaseModel):
    """Campaign creation schema"""

    name: str = Field(..., min_length=1, max_length=255)
    message_type: Literal["text", "template"] = "template"
    template_id: UUID | None = None
    waba_phone_id: UUID | None = None
    message_body: str | None = None

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
    message_type: Literal["text", "template"] | None = None
    template_id: UUID | None = None
    message_body: str | None = None


class CampaignSchedule(BaseModel):
    """Campaign planning schema"""

    scheduled_at: datetime = Field(
        ..., description="ISO 8601 datetime when to start the campaign"
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"scheduled_at": "2024-12-31T12:00:00Z"}}
    )


class CampaignResponse(UUIDMixin, TimestampMixin):
    """Full information about the campaign"""

    name: str
    status: CampaignStatus
    message_type: str
    template_id: UUID | None = None
    waba_phone_id: UUID | None = None
    message_body: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    total_contacts: int
    sent_count: int
    delivered_count: int
    read_count: int = 0
    replied_count: int = 0
    failed_count: int

    # Автоматичний розрахунок прогресу при серіалізації
    @computed_field
    def progress_percent(self) -> float:
        if self.total_contacts == 0:
            return 0.0
        return round((self.sent_count / self.total_contacts) * 100, 2)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Black Friday",
                "status": "running",
                "message_type": "template",
                "total_contacts": 1000,
                "sent_count": 750,
                "delivered_count": 700,
                "read_count": 500,
                "replied_count": 50,
                "failed_count": 50,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        },
    )


class CampaignContactResponse(BaseModel):
    """Contact information in the campaign"""

    id: UUID
    contact_id: UUID
    phone_number: str = Field(validation_alias=AliasPath("contact", "phone_number"))
    name: str | None = Field(
        default=None, validation_alias=AliasPath("contact", "name")
    )
    status: CampaignDeliveryStatus
    error_message: str | None = None
    retry_count: int

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "contact_id": "789e4567-e89b-12d3-a456-426614174000",
                "phone_number": "380671234567",
                "name": "John Doe",
                "status": "sent",
                "error_message": None,
                "retry_count": 0,
            }
        },
    )


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
