import mimetypes
import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.meta import MetaClient
from src.core.config import settings
from src.repositories.message import MessageRepository
from src.schemas import MetaMedia, MetaMessage
from src.services.media.storage import StorageService


class MediaService:
    def __init__(
        self, session: AsyncSession, storage_service: StorageService, meta_client: MetaClient
    ):
        self.session = session
        self.storage = storage_service
        self.meta_client = meta_client
        self.messages = MessageRepository(session)

    async def handle_media_attachment(
        self, message_id: uuid.UUID, meta_msg: MetaMessage
    ):
        try:
            media_obj: MetaMedia | None = getattr(
                meta_msg, meta_msg.type, None)
            if not media_obj:
                return

            media_url_meta = await self.meta_client.get_media_url(media_obj.id)
            file_content = await self.meta_client.download_media_file(media_url_meta)

            mime_type = media_obj.mime_type or "application/octet-stream"
            ext = mimetypes.guess_extension(mime_type) or ".bin"
            filename = f"{uuid.uuid4()}{ext}"

            r2_key = f"whatsapp/{meta_msg.type}s/{filename}"

            await self.storage.upload_file(file_content, r2_key, mime_type)

            await self.messages.add_media_file(
                message_id=message_id,
                meta_media_id=media_obj.id,
                file_name=filename,
                file_mime_type=mime_type,
                file_size=len(file_content),
                caption=media_obj.caption,
                r2_key=r2_key,
                bucket_name=settings.R2_BUCKET_NAME,
            )

            logger.info(f"Media saved: {r2_key} for msg {message_id}")

        except Exception as e:
            logger.error(f"Media processing failed for msg {message_id}: {e}")
