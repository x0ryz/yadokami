import uuid
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.models import CampaignStatus, ContactStatus, MessageDirection, MessageStatus


class WhatsAppMessage(BaseModel):
    phone_number: str
    type: Literal["text", "template"]
    body: str
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class MetaProfile(BaseModel):
    name: str


class MetaContact(BaseModel):
    wa_id: str
    profile: MetaProfile


class MetaMedia(BaseModel):
    id: str
    mime_type: Optional[str] = None
    sha256: Optional[str] = None
    caption: Optional[str] = None


class MetaText(BaseModel):
    body: str


class MetaMessage(BaseModel):
    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[MetaText] = None
    image: Optional[MetaMedia] = None
    video: Optional[MetaMedia] = None
    audio: Optional[MetaMedia] = None
    voice: Optional[MetaMedia] = None
    document: Optional[MetaMedia] = None
    sticker: Optional[MetaMedia] = None


class MetaStatus(BaseModel):
    id: str
    status: str
    timestamp: str
    recipient_id: str
    errors: Optional[List[dict]] = None


class MetaValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: List[MetaContact] = []
    messages: List[MetaMessage] = []
    statuses: List[MetaStatus] = []


class MetaChange(BaseModel):
    value: MetaValue
    field: str


class MetaEntry(BaseModel):
    id: str
    changes: List[MetaChange] = []


class MetaWebhookPayload(BaseModel):
    object: str
    entry: List[MetaEntry] = []


class WabaSyncRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class WebhookEvent(BaseModel):
    payload: dict[str, Any]


class MediaFileResponse(BaseModel):
    id: uuid.UUID
    file_name: str
    file_mime_type: str
    caption: str | None = None
    url: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    wamid: str | None = None
    direction: MessageDirection
    status: MessageStatus
    message_type: str
    body: str | None = None
    created_at: datetime | None = None
    media_files: list[MediaFileResponse] = []

    class Config:
        from_attributes = True


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
    """Schema for updating campaign"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    message_type: Optional[Literal["text", "template"]] = None
    template_id: Optional[uuid.UUID] = None
    message_body: Optional[str] = None


class CampaignSchedule(BaseModel):
    """Schema for scheduling a campaign"""

    scheduled_at: datetime = Field(
        ..., description="ISO 8601 datetime when to start the campaign"
    )

    class Config:
        json_schema_extra = {"example": {"scheduled_at": "2025-12-26T10:00:00Z"}}


class CampaignStats(BaseModel):
    """Campaign statistics"""

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
    """Full campaign response"""

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


class ContactImport(BaseModel):
    """Single contact for import"""

    phone_number: str
    name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ContactImportResult(BaseModel):
    """Result of contact import"""

    total: int
    imported: int
    skipped: int
    errors: List[str] = Field(default_factory=list)


class CampaignContactResponse(BaseModel):
    """Campaign contact link response"""

    id: uuid.UUID
    contact_id: uuid.UUID
    phone_number: str
    name: Optional[str] = None
    status: ContactStatus
    error_message: Optional[str] = None
    retry_count: int

    class Config:
        from_attributes = True
