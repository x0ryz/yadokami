from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WebhookEvent(BaseModel):
    payload: dict[str, Any]


class MetaBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class MetaProfile(MetaBaseModel):
    name: str


class MetaContact(MetaBaseModel):
    wa_id: str
    profile: MetaProfile | None = None


class MetaMedia(MetaBaseModel):
    id: str
    mime_type: str | None = None
    sha256: str | None = None
    caption: str | None = None
    filename: str | None = None


class MetaText(MetaBaseModel):
    body: str


class MetaLocation(MetaBaseModel):
    latitude: float
    longitude: float
    name: str | None = None
    address: str | None = None


class MetaReaction(MetaBaseModel):
    message_id: str
    emoji: str


class MetaContext(MetaBaseModel):
    from_: str = Field(alias="from")
    id: str


class InteractiveButtonReply(MetaBaseModel):
    id: str
    title: str


class InteractiveListReply(MetaBaseModel):
    id: str
    title: str
    description: str | None = None


class MetaInteractive(MetaBaseModel):
    type: Literal["button_reply", "list_reply"]
    button_reply: InteractiveButtonReply | None = None
    list_reply: InteractiveListReply | None = None


class MetaReferral(MetaBaseModel):
    source_url: str
    source_type: str
    source_id: str
    headline: str
    body: str
    media_type: str
    image_url: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None


class MetaContactName(MetaBaseModel):
    formatted_name: str
    first_name: str | None = None
    last_name: str | None = None


class MetaContactPhone(MetaBaseModel):
    phone: str | None = None
    type: str | None = None
    wa_id: str | None = None


class MetaContactPayload(MetaBaseModel):
    name: MetaContactName | None = None
    phones: list[MetaContactPhone] = Field(default_factory=list)


class MetaMessage(MetaBaseModel):
    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    context: MetaContext | None = None
    text: MetaText | None = None
    image: MetaMedia | None = None
    video: MetaMedia | None = None
    audio: MetaMedia | None = None
    voice: MetaMedia | None = None
    document: MetaMedia | None = None
    sticker: MetaMedia | None = None
    location: MetaLocation | None = None
    interactive: MetaInteractive | None = None
    reaction: MetaReaction | None = None
    contacts: list[MetaContactPayload] | None = None
    referral: MetaReferral | None = None
    errors: list[dict[str, Any]] | None = None


class MetaStatus(MetaBaseModel):
    id: str
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: str
    recipient_id: str
    errors: list[dict[str, Any]] | None = None
    pricing: dict[str, Any] | None = None
    conversation: dict[str, Any] | None = None


class MetaTemplateUpdate(MetaBaseModel):
    event: str
    message_template_id: str
    message_template_name: str
    message_template_language: str
    reason: str | None = None


class MetaPhoneNumberQualityUpdate(MetaBaseModel):
    display_phone_number: str
    event: str
    current_limit: str


class MetaAccountReviewUpdate(MetaBaseModel):
    decision: str
    update_time: str | None = None


class MetaAccountBanUpdate(MetaBaseModel):
    ban_info: dict[str, Any] | None = None


class MetaValue(MetaBaseModel):
    messaging_product: str
    metadata: dict[str, Any]

    contacts: list[MetaContact] = Field(default_factory=list)
    messages: list[MetaMessage] = Field(default_factory=list)
    statuses: list[MetaStatus] = Field(default_factory=list)

    message_template_status_update: MetaTemplateUpdate | None = None
    phone_number_quality_update: MetaPhoneNumberQualityUpdate | None = None
    account_review_update: MetaAccountReviewUpdate | None = None
    account_update: MetaAccountBanUpdate | None = None


class MetaChange(MetaBaseModel):
    value: MetaValue
    field: str


class MetaEntry(MetaBaseModel):
    id: str
    changes: list[MetaChange] = Field(default_factory=list)


class MetaWebhookPayload(MetaBaseModel):
    object: str
    entry: list[MetaEntry] = Field(default_factory=list)
