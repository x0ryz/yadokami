from typing import AsyncGenerator

import httpx
from aiolimiter import AsyncLimiter
from cachetools import TTLCache
from faststream import Context, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.meta import MetaClient
from src.core.database import async_session_maker
from src.core.logger import setup_logging
from src.repositories.waba import WabaRepository
from src.services.campaign.sender import CampaignSenderService
from src.services.media.service import MediaService
from src.services.media.storage import StorageService
from src.services.messaging.processor import MessageProcessorService
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService
from src.services.sync import SyncService

logger = setup_logging()

limiter = AsyncLimiter(10, 1)
credentials_cache: TTLCache = TTLCache(maxsize=100, ttl=300)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def _get_meta_credentials() -> tuple[str | None, str | None]:
    cache_key = "meta_credentials"
    if cache_key in credentials_cache:
        return credentials_cache[cache_key]

    token, base_url = None, None
    try:
        async with async_session_maker() as session:
            account = await WabaRepository(session).get_credentials()
            if account:
                token = account.access_token
                if hasattr(account, "graph_api_version") and account.graph_api_version:
                    base_url = f"https://graph.facebook.com/{account.graph_api_version}"
    except Exception as e:
        logger.error(f"Failed to fetch WABA credentials: {e}")

    credentials_cache[cache_key] = (token, base_url)
    return token, base_url


async def get_worker_meta_client(
    http_client: httpx.AsyncClient = Context("http_client"),
) -> MetaClient:
    token, base_url = await _get_meta_credentials()
    if not token:
        raise ValueError("Meta credentials not found")
    return MetaClient(client=http_client, base_url=base_url, token=token)


# --- Service Assemblers ---


async def get_message_sender_service(
    session: AsyncSession = Depends(get_session),
    meta_client: MetaClient = Depends(get_worker_meta_client),
) -> MessageSenderService:
    return MessageSenderService(
        session, meta_client, NotificationService(), StorageService()
    )


async def get_campaign_sender_service(
    session: AsyncSession = Depends(get_session),
    message_sender: MessageSenderService = Depends(get_message_sender_service),
) -> CampaignSenderService:
    return CampaignSenderService(session, message_sender, NotificationService())


async def get_processor_service(
    session: AsyncSession = Depends(get_session),
    meta_client: MetaClient = Depends(get_worker_meta_client),
) -> MessageProcessorService:
    media_service = MediaService(session, StorageService(), meta_client)
    return MessageProcessorService(session, media_service, NotificationService())


async def get_sync_service(
    session: AsyncSession = Depends(get_session),
    meta_client: MetaClient = Depends(get_worker_meta_client),
) -> SyncService:
    return SyncService(session, meta_client)
