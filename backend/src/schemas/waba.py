from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .base import TimestampMixin, UUIDMixin


class WabaAccountRequest(BaseModel):
    """Схема для налаштування WABA акаунту"""

    waba_id: str
    name: str = "My Business"

    access_token: str | None = None
    app_secret: str | None = None
    verify_token: str | None = None
    graph_api_version: str = "v21.0"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "waba_id": "1234567890",
                "name": "My Business",
                "access_token": "EAAG...",
                "app_secret": "a1b2...",
                "verify_token": "my_secret_verify_token",
                "graph_api_version": "v21.0",
            }
        }
    )


class WabaSyncRequest(BaseModel):
    """WABA sync request"""

    request_id: str = Field(default_factory=lambda: str(uuid4()))

    model_config = ConfigDict(json_schema_extra={"example": {"request_id": "sync_123"}})


class WabaAccountResponse(UUIDMixin):
    """WABA account information"""

    waba_id: str
    name: str
    account_review_status: str | None = None
    business_verification_status: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "waba_id": "1234567890",
                "name": "My Business",
                "account_review_status": "APPROVED",
                "business_verification_status": "VERIFIED",
            }
        },
    )


class WabaPhoneResponse(UUIDMixin, TimestampMixin):
    """WABA phone number information"""

    waba_id: UUID
    phone_number_id: str
    display_phone_number: str
    status: str | None = None
    quality_rating: str
    messaging_limit_tier: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "waba_id": "789e4567-e89b-12d3-a456-426614174000",
                "phone_number_id": "1234567890",
                "display_phone_number": "+380671234567",
                "status": "CONNECTED",
                "quality_rating": "GREEN",
                "messaging_limit_tier": "TIER_1K",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        },
    )


class WabaSyncResponse(BaseModel):
    """Sync request response"""

    status: str = "sync_started"
    request_id: str
    message: str = "WABA sync initiated"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "sync_started",
                "request_id": "sync_123",
                "message": "WABA sync initiated",
            }
        }
    )
