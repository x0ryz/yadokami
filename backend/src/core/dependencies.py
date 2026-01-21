from typing import AsyncGenerator

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.meta import MetaClient
from src.core.database import async_session_maker
from src.repositories.waba import WabaRepository
from src.services.campaign.importer import ContactImportService
from src.services.campaign.sender import CampaignSenderService
from src.services.dashboard import DashboardService
from src.services.media.service import MediaService
from src.services.media.storage import StorageService
from src.services.messaging.chat import ChatService
from src.services.messaging.processor import MessageProcessorService
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService
from src.services.sync import SyncService


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async session."""
    async with async_session_maker() as session:
        yield session


async def get_meta_client(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[MetaClient, None]:
    """Get Meta API client instance with dynamic credentials from DB."""

    token = None
    base_url = None

    account = await WabaRepository(session).get_credentials()
    if account:
        if account.access_token:
            token = account.access_token

        if hasattr(account, "graph_api_version") and account.graph_api_version:
            base_url = f"https://graph.facebook.com/{account.graph_api_version}"

    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:
        yield MetaClient(client=client, base_url=base_url)


def get_storage_service() -> StorageService:
    """Get storage service for media file handling."""
    return StorageService()


def get_notification_service() -> NotificationService:
    """Get notification service for WebSocket updates."""
    return NotificationService()


def get_sync_service(
    session: AsyncSession = Depends(get_session),
    meta_client: MetaClient = Depends(get_meta_client),
) -> SyncService:
    """Get service for syncing WABA data from Meta."""
    return SyncService(session=session, meta_client=meta_client)


def get_media_service(
    session: AsyncSession = Depends(get_session),
    storage_service: StorageService = Depends(get_storage_service),
    meta_client: MetaClient = Depends(get_meta_client),
) -> MediaService:
    """Get service for handling media attachments."""
    return MediaService(
        session=session, storage_service=storage_service, meta_client=meta_client
    )


def get_message_sender_service(
    session: AsyncSession = Depends(get_session),
    meta_client: MetaClient = Depends(get_meta_client),
    notifier: NotificationService = Depends(get_notification_service),
    storage: StorageService = Depends(get_storage_service),
) -> MessageSenderService:
    """Get service for sending WhatsApp messages."""
    return MessageSenderService(
        session=session, meta_client=meta_client, notifier=notifier, storage=storage
    )


def get_chat_service(
    session: AsyncSession = Depends(get_session),
    notifier: NotificationService = Depends(get_notification_service),
    storage: StorageService = Depends(get_storage_service),
) -> ChatService:
    """Get service for managing chat history."""
    return ChatService(session=session, notifier=notifier, storage=storage)


def get_message_processor_service(
    session: AsyncSession = Depends(get_session),
    media_service: MediaService = Depends(get_media_service),
    notifier: NotificationService = Depends(get_notification_service),
) -> MessageProcessorService:
    """Get service for processing webhook messages."""
    return MessageProcessorService(
        session=session, media_service=media_service, notifier=notifier
    )


def get_contact_import_service(
    session: AsyncSession = Depends(get_session),
) -> ContactImportService:
    """Get service for importing contacts from CSV/Excel."""
    return ContactImportService(session=session)


def get_campaign_sender_service(
    session: AsyncSession = Depends(get_session),
    message_sender: MessageSenderService = Depends(get_message_sender_service),
    notifier: NotificationService = Depends(get_notification_service),
) -> CampaignSenderService:
    """Get service for managing campaign sending."""
    return CampaignSenderService(
        session=session, message_sender=message_sender, notifier=notifier
    )


def get_dashboard_service(
    session: AsyncSession = Depends(get_session),
) -> DashboardService:
    """Get service for dashboard statistics."""
    return DashboardService(session=session)
