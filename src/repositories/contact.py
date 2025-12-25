from uuid import UUID

from sqlmodel import select

from src.models import Contact
from src.repositories.base import BaseRepository


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
            self.session.flush()
        return contact
