import uuid
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.models import MessageDirection, MessageStatus


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
