from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.models.base import MessageDirection, MessageStatus

from .base import UUIDMixin


class MessageCreate(BaseModel):
    """Schema for creating a message via API"""

    phone_number: str = Field(..., description="Recipient phone number")
    type: Literal["text", "template"] = "text"
    body: str = Field(..., description="Message text or template ID")
    template_id: UUID | None = None
    reply_to_message_id: UUID | None = None
    phone_id: UUID | None = None
    scheduled_at: datetime | None = Field(
        default=None, 
        description="ISO 8601 datetime to schedule message for future delivery"
    )


class WhatsAppMessage(BaseModel):
    """Internal schema for sending messages via worker"""

    phone_number: str
    type: Literal["text", "template", "image",
                  "video", "audio", "document", "sticker"]
    body: str
    reply_to_message_id: UUID | None = None
    phone_id: UUID | None = None
    request_id: str = Field(default_factory=lambda: str(uuid4()))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone_number": "380671234567",
                "type": "text",
                "body": "Hello from API",
                "request_id": "req_123",
            }
        }
    )


class MediaFileResponse(BaseModel):
    """Media file information"""

    id: UUID
    file_name: str
    file_mime_type: str
    caption: str | None = None
    url: str = Field(..., description="Presigned URL for download")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "file_name": "image.jpg",
                "file_mime_type": "image/jpeg",
                "caption": "Photo caption",
                "url": "https://storage.example.com/...",
            }
        },
    )


class MessageResponse(UUIDMixin):
    """Full message information"""

    wamid: str | None = None
    direction: MessageDirection
    status: MessageStatus
    message_type: str
    body: str | None = None
    created_at: datetime
    sent_at: datetime | None = None
    scheduled_at: datetime | None = None
    reply_to_message_id: UUID | None = None
    reaction: str | None = None
    media_files: list[MediaFileResponse] = Field(default_factory=list)
    error_code: int | None = None
    error_message: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "wamid": "wamid.ABC123",
                "direction": "outbound",
                "status": "delivered",
                "message_type": "text",
                "body": "Hello, World!",
                "reply_to_message_id": "123e4567-e89b-12d3-a456-426614174000",
                "reaction": "👍",
                "created_at": "2024-01-15T10:30:00Z",
                "media_files": [],
                "error_code": None,
                "error_message": None,
            }
        },
    )


class MessageSendResponse(BaseModel):
    """Response for send request"""

    status: str = "sent"
    message_id: UUID
    request_id: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "sent",
                "message_id": "123e4567-e89b-12d3-a456-426614174000",
                "request_id": "req_123",
            }
        }
    )


class MediaSendRequest(BaseModel):
    """Schema for the media sending task (messages.media_send)"""

    phone_number: str
    file_path: str
    filename: str
    mime_type: str
    caption: str | None = None
    request_id: str | None = None


class MediaDownloadRequest(BaseModel):
    """Schema for the media download task (media.download)"""

    message_id: str
    meta_media_id: str
    media_type: str
    mime_type: str
    caption: str | None = None
