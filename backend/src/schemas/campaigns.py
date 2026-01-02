import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field
from src.models.base import CampaignStatus, ContactStatus


class CampaignCreate(BaseModel):
    """Schema for creating a new campaign"""

    name: str = Field(..., min_length=1, max_length=255)
    message_type: Literal["text", "template"] = "template"
    template_id: Optional[uuid.UUID] = None
    message_body: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Black Friday Campaign",
                "message_type": "template",
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    message_type: Optional[Literal["text", "template"]] = None
    template_id: Optional[uuid.UUID] = None
    message_body: Optional[str] = None


class CampaignSchedule(BaseModel):
    scheduled_at: datetime = Field(
        ..., description="ISO 8601 datetime when to start the campaign"
    )


class CampaignStats(BaseModel):
    id: uuid.UUID
    name: str
    status: CampaignStatus
    total_contacts: int
    sent_count: int
    delivered_count: int
    failed_count: int
    progress_percent: float
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: CampaignStatus
    message_type: str
    template_id: Optional[uuid.UUID] = None
    message_body: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_contacts: int
    sent_count: int
    delivered_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignContactResponse(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    phone_number: str
    name: Optional[str] = None
    status: ContactStatus
    error_message: Optional[str] = None
    retry_count: int

    class Config:
        from_attributes = True
