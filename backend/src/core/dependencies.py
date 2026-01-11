from typing import AsyncGenerator

import httpx
from fastapi import Depends

from src.clients.meta import MetaClient
from src.core.config import settings
from src.core.database import async_session_maker
from src.core.uow import UnitOfWork
from src.services.campaign.importer import ContactImportService
from src.services.campaign.sender import CampaignSenderService
from src.services.media.service import MediaService
from src.services.media.storage import StorageService
from src.services.messaging.chat import ChatService
from src.services.messaging.processor import MessageProcessorService
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService
from src.services.sync import SyncService


def get_uow() -> UnitOfWork:
    """Get Unit of Work instance with session factory."""
    return UnitOfWork(session_factory=async_session_maker)


async def get_meta_client() -> AsyncGenerator[MetaClient, None]:
    """Get Meta API client instance."""
    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {settings.META_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:
        yield MetaClient(client=client)


def get_storage_service() -> StorageService:
    """Get storage service for media file handling."""
    return StorageService()


def get_notification_service() -> NotificationService:
    """Get notification service for WebSocket updates."""
    return NotificationService()


async def get_sync_service(
    meta_client: MetaClient = Depends(get_meta_client),
) -> AsyncGenerator[SyncService, None]:
    """Get service for syncing WABA data from Meta."""
    async with async_session_maker() as session:
        yield SyncService(session=session, meta_client=meta_client)


def get_media_service(
    uow: UnitOfWork = Depends(get_uow),
    storage_service: StorageService = Depends(get_storage_service),
    meta_client: MetaClient = Depends(get_meta_client),
) -> MediaService:
    """Get service for handling media attachments."""
    return MediaService(
        uow=uow, storage_service=storage_service, meta_client=meta_client
    )


def get_message_sender_service(
    uow: UnitOfWork = Depends(get_uow),
    meta_client: MetaClient = Depends(get_meta_client),
    notifier: NotificationService = Depends(get_notification_service),
    storage: StorageService = Depends(get_storage_service),
) -> MessageSenderService:
    """Get service for sending WhatsApp messages."""
    return MessageSenderService(
        uow=uow, meta_client=meta_client, notifier=notifier, storage=storage
    )


def get_chat_service(
    uow: UnitOfWork = Depends(get_uow),
    notifier: NotificationService = Depends(get_notification_service),
    storage: StorageService = Depends(get_storage_service),
) -> ChatService:
    """Get service for managing chat history."""
    return ChatService(uow=uow, notifier=notifier, storage=storage)


def get_message_processor_service(
    uow: UnitOfWork = Depends(get_uow),
    media_service: MediaService = Depends(get_media_service),
    notifier: NotificationService = Depends(get_notification_service),
) -> MessageProcessorService:
    """Get service for processing webhook messages."""
    return MessageProcessorService(
        uow=uow, media_service=media_service, notifier=notifier
    )


def get_contact_import_service(
    uow: UnitOfWork = Depends(get_uow),
) -> ContactImportService:
    """Get service for importing contacts from CSV/Excel."""
    return ContactImportService(uow=uow)


def get_campaign_sender_service(
    uow: UnitOfWork = Depends(get_uow),
    message_sender: MessageSenderService = Depends(get_message_sender_service),
    notifier: NotificationService = Depends(get_notification_service),
) -> CampaignSenderService:
    """Get service for managing campaign sending."""
    return CampaignSenderService(
        uow=uow, message_sender=message_sender, notifier=notifier
    )
