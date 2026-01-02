from typing import Any, List, Optional

from pydantic import BaseModel, Field


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


class WebhookEvent(BaseModel):
    payload: dict[str, Any]
