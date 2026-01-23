from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import selectinload

from src.models import Contact, ContactStatus, Tag, get_utc_now
from src.repositories.base import BaseRepository
from src.repositories.tag import TagRepository
from src.schemas.contacts import ContactCreate, ContactUpdate


class ContactRepository(BaseRepository[Contact]):
    def __init__(self, session):
        super().__init__(session, Contact)

    async def get_by_id(self, id: UUID) -> Contact | None:
        query = (
            select(Contact).where(Contact.id == id).options(
                selectinload(Contact.tags))
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_phone(self, phone_number: str) -> Contact | None:
        stmt = select(Contact).where(Contact.phone_number == phone_number).options(
            selectinload(Contact.tags)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create(self, phone_number: str) -> Contact:
        contact = await self.get_by_phone(phone_number)
        if not contact:
            contact = Contact(phone_number=phone_number, custom_data={})
            self.session.add(contact)
            await self.session.flush()

            # Явно завантажуємо теги для нового контакту
            await self.session.refresh(contact, ["tags"])
        return contact

    async def get_paginated(
        self,
        limit: int,
        offset: int,
        tag_ids: list[UUID] | None = None,
        status: ContactStatus | None = None,
        show_only_with_tags: bool = False,
    ) -> list[Contact]:
        stmt = select(Contact).options(
            selectinload(Contact.last_message), selectinload(Contact.tags)
        )

        if status:
            stmt = stmt.where(Contact.status == status)
        else:
            stmt = stmt.where(
                Contact.status.not_in(
                    [ContactStatus.BLOCKED, ContactStatus.ARCHIVED])
            )

        if tag_ids:
            stmt = stmt.where(Contact.tags.any(Tag.id.in_(tag_ids)))
        elif show_only_with_tags:
            # Показуємо тільки контакти, які мають хоча б один тег
            stmt = stmt.where(Contact.tags.any())

        stmt = stmt.order_by(
            desc(Contact.unread_count),
            desc(Contact.last_message_at).nulls_last()
        ).offset(offset).limit(limit)

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

        contact = Contact(
            **data.model_dump(exclude={"tag_ids"}), source="manual")
        if not contact.custom_data:
            contact.custom_data = {}
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
        tags_changed = False

        if "tag_ids" in update_data:
            tag_ids = update_data.pop("tag_ids")
            tags_changed = True

            if not tag_ids:
                contact.tags = []
            else:
                tags_query = select(Tag).where(Tag.id.in_(tag_ids))
                tags_result = await self.session.execute(tags_query)
                contact.tags = list(tags_result.scalars().all())

            # Перевіряємо чи є тег "Замовлення виконано" - якщо є, архівуємо контакт
            has_completed_tag = any(
                tag.name == "Замовлення виконано" for tag in contact.tags)
            if has_completed_tag:
                contact.status = ContactStatus.ARCHIVED
            else:
                # Перевіряємо чи потрібно архівувати якщо немає тегів
                await self.check_and_archive_if_no_tags(contact)

        for key, value in update_data.items():
            setattr(contact, key, value)

        contact.updated_at = get_utc_now()
        self.session.add(contact)

        # Нотифікуємо про зміну тегів
        if tags_changed:
            from src.services.notifications.service import NotificationService
            notifier = NotificationService()
            tags_data = [
                {"id": str(tag.id), "name": tag.name, "color": tag.color} for tag in contact.tags]
            await notifier.notify_contact_tags_changed(contact.id, contact.phone_number, tags_data)

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
        contact.last_message_at = get_utc_now()
        contact.last_incoming_message_at = get_utc_now()
        self.add(contact)
        return contact

    async def set_auto_tag(self, contact: Contact, tag_name: str, notify: bool = True) -> None:
        """Automatically set a tag to the contact, replacing old auto-tags."""
        tag_repo = TagRepository(self.session)

        # Визначаємо системні теги які автоматично замінюються
        auto_system_tags = ["Потребує відповіді", "Очікуємо на відповідь"]

        # Теги які НЕ можна видаляти автоматично (тільки адмін вручну)
        manual_tags = ["Новий користувач", "Нове замовлення",
                       "Оплачено", "Замовлення виконано"]

        # Отримуємо новий тег
        new_tag = await tag_repo.get_or_create_tag(tag_name)

        # Видаляємо тільки автоматичні системні теги (НЕ чіпаємо manual_tags)
        contact.tags = [
            tag for tag in contact.tags if tag.name not in auto_system_tags]

        # Додаємо новий системний тег
        if new_tag not in contact.tags:
            contact.tags.append(new_tag)

        # Якщо у контакта є теги, він має бути активним
        if contact.tags:
            contact.status = ContactStatus.ACTIVE

        self.add(contact)

        # Нотифікуємо про зміну тегів (якщо треба)
        if notify:
            from src.services.notifications.service import NotificationService
            notifier = NotificationService()
            tags_data = [
                {"id": str(tag.id), "name": tag.name, "color": tag.color} for tag in contact.tags]
            await notifier.notify_contact_tags_changed(contact.id, contact.phone_number, tags_data)

    async def check_and_archive_if_no_tags(self, contact: Contact) -> None:
        """Архівує контакт, якщо у нього немає тегів."""
        if not contact.tags:
            contact.status = ContactStatus.ARCHIVED
            self.add(contact)

    async def has_received_template_message(self, contact_id: UUID) -> bool:
        """Перевіряє чи отримував контакт шаблонні повідомлення."""
        from src.models import Message, MessageDirection

        stmt = select(Message).where(
            Message.contact_id == contact_id,
            Message.direction == MessageDirection.OUTBOUND,
            Message.template_id.isnot(None)
        ).limit(1)

        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

    async def get_inbound_message_count(self, contact_id: UUID) -> int:
        """Повертає кількість вхідних повідомлень від контакту."""
        from src.models import Message, MessageDirection

        stmt = select(func.count()).where(
            Message.contact_id == contact_id,
            Message.direction == MessageDirection.INBOUND
        )

        result = await self.session.execute(stmt)
        return result.scalar() or 0
