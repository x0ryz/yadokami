from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


class ContactTagLink(SQLModel, table=True):
    __tablename__ = "contact_tags"

    contact_id: UUID = Field(foreign_key="contacts.id", primary_key=True)
    tag_id: UUID = Field(foreign_key="tags.id", primary_key=True)


class Tag(SQLModel, table=True):
    __tablename__ = "tags"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    color: str = Field(default="#808080")

    contacts: list["Contact"] = Relationship(
        back_populates="tags", link_model=ContactTagLink
    )
