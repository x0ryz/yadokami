from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field(default="#808080", pattern=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagResponse(TagBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
