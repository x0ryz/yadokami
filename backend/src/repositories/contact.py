from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import desc, or_, select
from src.models import Contact, get_utc_now
from src.repositories.base import BaseRepository
from src.schemas.contacts import ContactCreate, ContactUpdate


class ContactRepository(BaseRepository[Contact]):
    def __init__(self, session):
        super().__init__(session, Contact)

    async def get_by_id(self, contact_id: UUID) -> Contact | None:
        return await self.session.get(Contact, contact_id)

    async def get_by_phone(self, phone_number: str) -> Contact | None:
        stmt = select(Contact).where(Contact.phone_number == phone_number)
        return (await self.session.exec(stmt)).first()

    async def get_or_create(self, phone_number: str) -> Contact:
        contact = await self.get_by_phone(phone_number)
        if not contact:
            contact = Contact(phone_number=phone_number)
            self.session.add(contact)
            await self.session.flush()
        return contact

    async def get_paginated(self, limit: int, offset: int) -> list[Contact]:
        """Get contacts sorted by unread count and last activity"""
        stmt = (
            select(Contact)
            .options(selectinload(Contact.last_message))
            .order_by(desc(Contact.unread_count), desc(Contact.last_message_at))
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.exec(stmt)).all()

    async def search(self, q: str, limit: int) -> list[Contact]:
        """Search by phone or name"""
        stmt = (
            select(Contact)
            .where(or_(Contact.phone_number.contains(q), Contact.name.ilike(f"%{q}%")))
            .limit(limit)
        )
        return (await self.session.exec(stmt)).all()

    async def create_manual(self, data: ContactCreate) -> Contact:
        if await self.get_by_phone(data.phone_number):
            return None

        contact = Contact(**data.model_dump(), source="manual")
        self.session.add(contact)
        return contact

    async def update(self, contact_id: UUID, data: ContactUpdate) -> Contact | None:
        contact = await self.get_by_id(contact_id)
        if not contact:
            return None

        update_data = data.model_dump(exclude_unset=True)
        contact.sqlmodel_update(update_data)

        contact.updated_at = get_utc_now()
        self.session.add(contact)
        return contact
