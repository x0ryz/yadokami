from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import desc, or_, select
from src.models import Contact, Tag, get_utc_now
from src.repositories.base import BaseRepository
from src.schemas.contacts import ContactCreate, ContactUpdate


class ContactRepository(BaseRepository[Contact]):
    def __init__(self, session):
        super().__init__(session, Contact)

    async def get_by_id(self, contact_id: UUID) -> Contact | None:
        query = (
            select(Contact)
            .where(Contact.id == contact_id)
            .options(selectinload(Contact.tags))
        )
        result = await self.session.exec(query)
        return result.first()

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
            .options(selectinload(Contact.last_message), selectinload(Contact.tags))
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
            .options(selectinload(Contact.tags))
            .limit(limit)
        )
        return (await self.session.exec(stmt)).all()

    async def create_manual(self, data: ContactCreate) -> Contact:
        if await self.get_by_phone(data.phone_number):
            return None

        contact = Contact(**data.model_dump(exclude={"tag_ids"}), source="manual")
        if data.tag_ids:
            tags_query = select(Tag).where(Tag.id.in_(data.tag_ids))
            tags_result = await self.session.exec(tags_query)
            contact.tags = tags_result.scalars().all()

        self.session.add(contact)
        return contact

    async def update(self, contact_id: UUID, data: ContactUpdate) -> Contact | None:
        # Важливо: завантажуємо контакт разом з існуючими тегами,
        # щоб коректно працював механізм відстеження змін сесії
        contact = await self.get_by_id(contact_id)
        if not contact:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # 1. Перевіряємо, чи є tag_ids у даних для оновлення
        if "tag_ids" in update_data:
            tag_ids = update_data.pop(
                "tag_ids"
            )  # Видаляємо зі словника, щоб не ламав sqlmodel_update

            # 2. Якщо список порожній - очищаємо теги
            if not tag_ids:
                contact.tags = []
            else:
                # 3. Знаходимо об'єкти тегів у базі
                tags_query = select(Tag).where(Tag.id.in_(tag_ids))
                tags_result = await self.session.exec(tags_query)
                new_tags = tags_result.all()

                # 4. Присвоюємо нові об'єкти (SQLAlchemy сам розбереться, що додати/видалити в проміжній таблиці)
                contact.tags = list(new_tags)

        # Оновлюємо решту скалярних полів (name, email тощо)
        contact.sqlmodel_update(update_data)

        contact.updated_at = get_utc_now()
        self.session.add(contact)
        return contact
