from typing import Awaitable, Callable, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from src.clients.meta import MetaClient
from src.schemas import WhatsAppMessage

from .handle import WhatsAppHandlerService
from .send import WhatsAppSenderService


class WhatsAppService:
    """
    Unified Service Facade for Worker compatibility.
    """

    def __init__(
        self,
        session: AsyncSession,
        meta_client: MetaClient,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.sender = WhatsAppSenderService(session, meta_client, notifier)
        self.handler = WhatsAppHandlerService(session, meta_client, notifier)

    async def send_outbound_message(self, message: WhatsAppMessage):
        await self.sender.send_outbound_message(message)

    async def process_webhook(self, payload: dict):
        await self.handler.process_webhook(payload)
