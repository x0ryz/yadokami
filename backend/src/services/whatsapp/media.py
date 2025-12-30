import mimetypes
import uuid

from loguru import logger

from src.clients.meta import MetaClient
from src.core.config import settings
from src.core.uow import UnitOfWork
from src.models import MediaFile, Message
from src.schemas import MetaMedia, MetaMessage
from src.services.storage import StorageService


class WhatsAppMediaService:
    def __init__(
        self, uow: UnitOfWork, meta_client: MetaClient, storage_service: StorageService
    ):
        self.uow = uow
        self.meta_client = meta_client
        self.storage_service = StorageService()

    async def process_media_attachment(
        self,
        db_message: Message,
        meta_msg: MetaMessage,
    ) -> MediaFile | None:
        try:
            media_obj: MetaMedia | None = getattr(meta_msg, meta_msg.type, None)

            if not media_obj:
                logger.warning(f"No media data found for type {meta_msg.type}")
                return None

            media_id = media_obj.id
            caption = media_obj.caption

            media_url_meta = await self.meta_client.get_media_url(media_id)
            file_content = await self.meta_client.download_media_file(media_url_meta)

            mime_type = media_obj.mime_type or "application/octet-stream"
            ext = mimetypes.guess_extension(mime_type) or ".bin"

            filename = f"{uuid.uuid4()}{ext}"
            r2_key = f"whatsapp/{meta_msg.type}s/{filename}"

            await self.storage_service.upload_file(file_content, r2_key, mime_type)

            media_entry = await self.uow.media.create(
                auto_flush=True,
                message_id=db_message.id,
                meta_media_id=media_id,
                file_name=filename,
                file_mime_type=mime_type,
                file_size=len(file_content),
                caption=caption,
                r2_key=r2_key,
                bucket_name=settings.R2_BUCKET_NAME,
            )

            logger.info(f"Saved media to R2: {r2_key}")
            return media_entry

        except Exception as e:
            logger.error(f"Media processing failed for msg {db_message.id}: {e}")
            return None
