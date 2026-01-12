from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from src.models.base import ContactStatus, MessageDirection, MessageStatus
from src.schemas.tags import TagResponse

from .base import TimestampMixin, UUIDMixin


class ContactCreate(BaseModel):
    """Contact creation schema"""

    phone_number: str = Field(..., min_length=10, max_length=15)
    name: str | None = Field(default=None, max_length=255)
    link: str | None = Field(default=None)
    tag_ids: list[UUID] = Field(default=[])

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Remove all non-digit characters
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Phone must be 10-15 digits")
        return digits

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone_number": "380671234567",
                "name": "John Doe",
                "tag_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
            }
        }
    )


class ContactUpdate(BaseModel):
    """Contact update schema"""

    name: str | None = Field(default=None, max_length=255)
    link: str | None = Field(default=None)
    status: ContactStatus | None = None
    tag_ids: list[UUID] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Smith",
                "tag_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
            }
        }
    )


class ContactImport(BaseModel):
    """Schema for importing contacts from file"""

    phone_number: str
    link: str | None = None
    name: str | None = None
    tags: list[str] = Field(default_factory=list)


class ContactResponse(UUIDMixin, TimestampMixin):
    """Full contact information for API"""

    phone_number: str
    link: str | None = None
    name: str | None = None
    unread_count: int
    status: ContactStatus
    last_message_at: datetime | None = None
    source: str | None = None
    tags: list[TagResponse] = Field(default_factory=list)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "phone_number": "380671234567",
                "name": "John Doe",
                "unread_count": 3,
                "status": "new",
                "last_message_at": "2024-01-15T10:30:00Z",
                "source": "import_csv",
                "tags": [{"id": "...", "name": "vip", "color": "#FF0000"}],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        },
    )


class ContactListResponse(BaseModel):
    id: UUID
    link: str | None = None
    phone_number: str
    name: str | None = None
    unread_count: int
    last_message_at: datetime | None = None
    tags: list[TagResponse] = Field(default_factory=list)
    last_message: Any | None = Field(default=None, exclude=True)

    @computed_field
    def last_message_body(self) -> str | None:
        if not hasattr(self, "last_message") or not self.last_message:
            return None
        msg = self.last_message
        if msg.message_type == "text":
            return msg.body
        return f"[{msg.message_type}]"

    @computed_field
    def last_message_status(self) -> MessageStatus | None:
        return self.last_message.status if self.last_message else None

    @computed_field
    def last_message_direction(self) -> MessageDirection | None:
        return self.last_message.direction if self.last_message else None

    model_config = ConfigDict(from_attributes=True)


class ContactImportResult(BaseModel):
    """Contact import result"""

    total: int = Field(..., description="Total contacts in file")
    imported: int = Field(..., description="Successfully imported")
    skipped: int = Field(..., description="Skipped (duplicates)")
    errors: list[str] = Field(default_factory=list,
                              description="Error messages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 100,
                "imported": 95,
                "skipped": 3,
                "errors": [
                    "Row 5: Invalid phone number",
                    "Row 12: Missing phone number",
                ],
            }
        }
    )
