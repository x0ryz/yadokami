from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import selectinload

from src.models import Contact, ContactStatus, Tag, get_utc_now
from src.repositories.base import BaseRepository
from src.schemas.contacts import ContactCreate, ContactUpdate


class ContactRepository(BaseRepository[Contact]):
    def __init__(self, session):
        super().__init__(session, Contact)

    async def get_by_id(self, id: UUID) -> Contact | None:
        query = (
            select(Contact).where(Contact.id == id).options(selectinload(Contact.tags))
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_phone(self, phone_number: str) -> Contact | None:
        stmt = select(Contact).where(Contact.phone_number == phone_number)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create(self, phone_number: str) -> Contact:
        contact = await self.get_by_phone(phone_number)
        if not contact:
            contact = Contact(phone_number=phone_number)
            self.session.add(contact)
            await self.session.flush()
        return contact

    async def get_paginated(
        self,
        limit: int,
        offset: int,
        tag_ids: list[UUID] | None = None,
        status: ContactStatus | None = None,
    ) -> list[Contact]:
        stmt = select(Contact).options(
            selectinload(Contact.last_message), selectinload(Contact.tags)
        )

        if status:
            stmt = stmt.where(Contact.status == status)
        else:
            stmt = stmt.where(
                Contact.status.not_in([ContactStatus.BLOCKED, ContactStatus.ARCHIVED])
            )

        if tag_ids:
            stmt = stmt.where(Contact.tags.any(Tag.id.in_(tag_ids)))

        stmt = (
            stmt.order_by(
                desc(Contact.unread_count), desc(Contact.last_message_at).nulls_last()
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(self, q: str, limit: int) -> list[Contact]:
        stmt = (
            select(Contact)
            .where(or_(Contact.phone_number.contains(q), Contact.name.ilike(f"%{q}%")))
            .options(selectinload(Contact.tags))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_manual(self, data: ContactCreate) -> Contact | None:
        if await self.get_by_phone(data.phone_number):
            return None

        contact = Contact(**data.model_dump(exclude={"tag_ids"}), source="manual")
        if data.tag_ids:
            tags_query = select(Tag).where(Tag.id.in_(data.tag_ids))
            tags_result = await self.session.execute(tags_query)
            contact.tags = list(tags_result.scalars().all())

        self.session.add(contact)
        return contact

    async def update(self, contact_id: UUID, data: ContactUpdate) -> Contact | None:
        contact = await self.get_by_id(contact_id)
        if not contact:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "tag_ids" in update_data:
            tag_ids = update_data.pop("tag_ids")

            if not tag_ids:
                contact.tags = []
            else:
                tags_query = select(Tag).where(Tag.id.in_(tag_ids))
                tags_result = await self.session.execute(tags_query)
                contact.tags = list(tags_result.scalars().all())

        for key, value in update_data.items():
            setattr(contact, key, value)

        contact.updated_at = get_utc_now()
        self.session.add(contact)
        return contact

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(Contact)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_unread(self) -> int:
        stmt = select(func.count()).where(Contact.unread_count > 0)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def update_activity(self, phone: str) -> Contact:
        """Updates the last activity timestamp of a contact."""
        contact = await self.get_or_create(phone)
        contact.unread_count += 1
        contact.updated_at = get_utc_now()
        contact.last_incoming_message_at = get_utc_now()
        self.add(contact)
        return contact
