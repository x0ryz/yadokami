from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .base import TimestampMixin, UUIDMixin


class TemplateResponse(UUIDMixin, TimestampMixin):
    """Template information"""

    waba_id: UUID
    meta_template_id: str
    name: str
    language: str
    status: str
    category: str
    components: list[dict[str, Any]] = Field(default_factory=list)
    is_deleted: bool = False

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "waba_id": "789e4567-e89b-12d3-a456-426614174000",
                "meta_template_id": "1234567890",
                "name": "hello_world",
                "language": "en_US",
                "status": "APPROVED",
                "category": "MARKETING",
                "components": [{"type": "BODY", "text": "Hello {{1}}!"}],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        },
    )


class TemplateListResponse(UUIDMixin, TimestampMixin):
    """Template list with full details"""

    waba_id: UUID
    meta_template_id: str
    name: str
    language: str
    status: str
    category: str
    components: list[dict[str, Any]] = Field(default_factory=list)
    is_deleted: bool = False

    model_config = ConfigDict(from_attributes=True)
