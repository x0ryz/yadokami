from typing import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from src.repositories.contact import ContactRepository
from src.repositories.media import MediaRepository
from src.repositories.message import MessageRepository
from src.repositories.template import TemplateRepository
from src.repositories.waba import WabaRepository


class UnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self.session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self):
        self.session = self.session_factory()
        self.messages = MessageRepository(self.session)
        self.contacts = ContactRepository(self.session)
        self.waba = WabaRepository(self.session)
        self.templates = TemplateRepository(self.session)
        self.media = MediaRepository(self.session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()

        finally:
            await self.session.close()
