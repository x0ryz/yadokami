import mimetypes
import uuid
from typing import Awaitable, Callable, Optional

from loguru import logger
from src.clients.meta import MetaClient
from src.core.config import settings
from src.core.uow import UnitOfWork
from src.models import Message, MessageDirection, MessageStatus
from src.schemas import MetaMedia, MetaMessage, WhatsAppMessage
from src.services.storage import StorageService


class WhatsAppMessagingService:
    """
    Єдиний сервіс для роботи з контентом повідомлень (Inbound & Outbound).
    Об'єднує логіку відправки та обробки медіа.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        meta_client: MetaClient,
        storage_service: StorageService,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.uow = uow
        self.meta_client = meta_client
        self.storage_service = storage_service
        self.notifier = notifier

    # --- Outbound Logic (Send) ---

    async def send_outbound_message(self, message: WhatsAppMessage):
        """Відправка вихідного повідомлення через Meta API."""
        async with self.uow:
            contact = await self.uow.contacts.get_or_create(message.phone_number)
            waba_phone = await self.uow.waba.get_default_phone()

            if not waba_phone:
                logger.error("No WABA Phone numbers found in DB.")
                return

            # Обробка шаблонів
            template_db_id = None
            template_real_name = None

            if message.type == "template":
                requested_template_id = message.body
                template_obj = await self.uow.templates.get_active_by_id(
                    requested_template_id
                )

                if not template_obj:
                    logger.error(f"Template {requested_template_id} not found/active")
                    return

                template_db_id = template_obj.id
                template_real_name = template_obj.name

            body_to_save = (
                template_real_name if message.type == "template" else message.body
            )

            # Створення повідомлення в БД
            db_message = await self.uow.messages.create(
                auto_flush=True,
                waba_phone_id=waba_phone.id,
                contact_id=contact.id,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.PENDING,
                message_type=message.type,
                body=body_to_save,
                template_id=template_db_id,
            )

            await self._notify(
                "new_message", self._serialize_message(db_message, message.phone_number)
            )

            try:
                # Підготовка payload для Meta
                payload = self._build_meta_payload(
                    message, contact.phone_number, template_real_name
                )

                # Відправка
                result = await self.meta_client.send_message(
                    waba_phone.phone_number_id, payload
                )
                wamid = result.get("messages", [{}])[0].get("id")

                if wamid:
                    self.uow.messages.mark_as_sent(db_message, wamid)
                    await self.uow.commit()

                    await self._notify(
                        "status_update",
                        {
                            "id": str(db_message.id),
                            "wamid": wamid,
                            "old_status": "pending",
                            "new_status": "sent",
                            "phone": message.phone_number,
                        },
                    )
                    logger.success(
                        f"Message sent to {message.phone_number}. WAMID: {wamid}"
                    )

            except Exception as e:
                logger.exception(f"Failed to send message to {message.phone_number}")
                self.uow.messages.mark_as_failed(db_message)
                await self.uow.commit()

    # --- Inbound Logic (Process & Save Media) ---

    async def handle_incoming_message_content(
        self, msg: MetaMessage, contact_id: uuid.UUID, waba_id: uuid.UUID
    ) -> Message:
        """Зберігає вхідне повідомлення та завантажує медіа, якщо є."""

        # Визначаємо тіло повідомлення
        body = None
        if msg.type == "text" and msg.text:
            body = msg.text.body
        elif msg.type in ["image", "document", "video"] and getattr(msg, msg.type):
            body = getattr(msg, msg.type).caption

        # Створюємо повідомлення
        new_msg = await self.uow.messages.create(
            auto_flush=True,
            waba_phone_id=waba_id,
            contact_id=contact_id,
            direction=MessageDirection.INBOUND,
            status=MessageStatus.RECEIVED,
            wamid=msg.id,
            message_type=msg.type,
            body=body,
        )

        # Обробка медіа (якщо тип відповідний)
        if msg.type in ["image", "video", "document", "audio", "voice", "sticker"]:
            await self._process_media_attachment(new_msg, msg)

        return new_msg

    async def _process_media_attachment(
        self, db_message: Message, meta_msg: MetaMessage
    ):
        """Завантажує медіа з Meta, зберігає в R2 та створює запис у БД."""
        try:
            media_obj: MetaMedia | None = getattr(meta_msg, meta_msg.type, None)
            if not media_obj:
                return

            # Завантаження з Meta
            media_url_meta = await self.meta_client.get_media_url(media_obj.id)
            file_content = await self.meta_client.download_media_file(media_url_meta)

            # Визначення типу та імені
            mime_type = media_obj.mime_type or "application/octet-stream"
            ext = mimetypes.guess_extension(mime_type) or ".bin"
            filename = f"{uuid.uuid4()}{ext}"
            r2_key = f"whatsapp/{meta_msg.type}s/{filename}"

            # Завантаження в S3/R2
            await self.storage_service.upload_file(file_content, r2_key, mime_type)

            # Збереження в БД (через репозиторій повідомлень)
            await self.uow.messages.add_media_file(
                message_id=db_message.id,
                meta_media_id=media_obj.id,
                file_name=filename,
                file_mime_type=mime_type,
                file_size=len(file_content),
                caption=media_obj.caption,
                r2_key=r2_key,
                bucket_name=settings.R2_BUCKET_NAME,
            )

            logger.info(f"Saved media {r2_key} for msg {db_message.id}")

        except Exception as e:
            logger.error(f"Media processing failed for msg {db_message.id}: {e}")

    # --- Helpers ---

    def _build_meta_payload(
        self, message: WhatsAppMessage, to_phone: str, template_name: str | None
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": message.type,
        }
        if message.type == "text":
            payload["text"] = {"body": message.body}
        elif message.type == "template":
            payload["template"] = {
                "name": template_name,
                "language": {"code": "en_US"},
            }
        return payload

    async def _notify(self, event_type: str, data: dict):
        if self.notifier:
            await self.notifier({"event": event_type, "data": data})

    def _serialize_message(self, msg: Message, phone: str | None = None) -> dict:
        data = {
            "id": str(msg.id),
            "direction": msg.direction,
            "status": msg.status,
            "body": msg.body,
            "created_at": msg.created_at.isoformat(),
            "type": msg.message_type,
        }

        if phone:
            data["phone"] = phone
            data["to"] = phone

        return data
