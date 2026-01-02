from typing import List, Optional

from pydantic import BaseModel, Field


class ContactImport(BaseModel):
    phone_number: str
    name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ContactImportResult(BaseModel):
    total: int
    imported: int
    skipped: int
    errors: List[str] = Field(default_factory=list)
