from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
from src.repositories.message import MessageRepository
from src.repositories.tag import TagRepository
from src.repositories.template import TemplateRepository
from src.repositories.waba import WabaPhoneRepository, WabaRepository


class UnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self.session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self):
        self.session = self.session_factory()

        self.messages = MessageRepository(self.session)
        self.contacts = ContactRepository(self.session)
        self.waba = WabaRepository(self.session)
        self.waba_phones = WabaPhoneRepository(self.session)
        self.templates = TemplateRepository(self.session)
        self.campaigns = CampaignRepository(self.session)
        self.campaign_contacts = CampaignContactRepository(self.session)
        self.tags = TagRepository(self.session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self.session:
            return

        try:
            if exc_type:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.session.close()

    async def commit(self):
        """Manually commit changes"""
        if self.session:
            await self.session.commit()

    async def rollback(self):
        """Manually rollback changes"""
        if self.session:
            await self.session.rollback()
