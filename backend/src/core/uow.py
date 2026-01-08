from typing import Callable

from sqlmodel.ext.asyncio.session import AsyncSession
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
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
        self.campaigns = CampaignRepository(self.session)
        self.campaign_contacts = CampaignContactRepository(self.session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.session.close()

    async def commit(self):
        """Manually commit changes"""
        await self.session.commit()

    async def rollback(self):
        """Manually rollback changes"""
        await self.session.rollback()
