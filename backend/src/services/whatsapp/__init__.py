from typing import Awaitable, Callable, Optional

from loguru import logger
from src.clients.meta import MetaClient
from src.core.uow import UnitOfWork
from src.schemas import MetaWebhookPayload, WhatsAppMessage
from src.services.storage import StorageService

from .messaging import WhatsAppMessagingService
from .webhook import WhatsAppWebhookService


class WhatsAppService:
    """
    Головна точка входу для воркера.
    Ініціалізує MessagingService та WebhookService.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        meta_client: MetaClient,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        # Create storage service first
        storage = StorageService()

        # Initialize messaging service with storage
        self.messaging = WhatsAppMessagingService(uow, meta_client, storage, notifier)

        # Initialize webhook service
        self.webhook_handler = WhatsAppWebhookService(uow, self.messaging, notifier)

    async def send_outbound_message(self, message: WhatsAppMessage):
        """Делегування відправки."""
        await self.messaging.send_outbound_message(message)

    async def process_webhook(self, raw_payload: dict):
        """
        Валідує payload в Pydantic тут (на межі системи)
        і передає в чистий WebhookService.
        """
        try:
            # Валідація відбувається тут
            webhook = MetaWebhookPayload.model_validate(raw_payload)
            await self.webhook_handler.process_payload(webhook)
        except Exception as e:
            logger.error(f"Failed to validate or process webhook: {e}")
