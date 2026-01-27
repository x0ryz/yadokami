import mimetypes
import uuid
from datetime import datetime
from src.models.base import get_utc_now

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.meta import MetaClient, MetaPayloadBuilder
from src.core.config import settings
from src.models import Contact, Message, MessageDirection, MessageStatus
from src.repositories.contact import ContactRepository
from src.repositories.message import MessageRepository
from src.repositories.waba import WabaPhoneRepository
from src.schemas import WhatsAppMessage
from src.services.media.storage import StorageService
from src.services.notifications.service import NotificationService


class MessageSenderService:
    """
    Message sending service.

    Each public method commits its changes.
    """

    def __init__(
        self,
        session: AsyncSession,
        meta_client: MetaClient,
        notifier: NotificationService,
        storage: StorageService | None = None,
    ):
        self.session = session
        self.meta_client = meta_client
        self.notifier = notifier
        self.storage = storage or StorageService()

        # Initialize repositories
        self.contacts = ContactRepository(session)
        self.messages = MessageRepository(session)
        self.waba_phones = WabaPhoneRepository(session)

    async def send_manual_message(self, message: WhatsAppMessage):
        """Send a manual message (from API)."""
        contact = await self.contacts.get_or_create(message.phone_number)

        template_id = None
        template_name = None
        template_language_code = None

        if message.type == "template":
            from src.repositories.template import TemplateRepository

            template_repo = TemplateRepository(self.session)
            template = await template_repo.get_active_by_id(message.body)
            if template:
                template_id = template.id
                template_name = template.name
                template_language_code = template.language
            else:
                logger.error(f"Template {message.body} not found")
                return

        await self.send_to_contact(
            contact=contact,
            message_type=message.type,
            body=message.body,
            template_id=template_id,
            template_name=template_name,
            template_language_code=template_language_code,
            is_campaign=False,
            reply_to_message_id=message.reply_to_message_id,
            phone_id=str(message.phone_id) if message.phone_id else None,
        )

        await self.session.commit()

    async def create_scheduled_message(
        self,
        phone_number: str,
        message_type: str,
        body: str,
        scheduled_at: datetime,
        reply_to_message_id: uuid.UUID | None = None,
        phone_id: str | None = None,
    ):
        """Create a scheduled message in the database."""
        contact = await self.contacts.get_or_create(phone_number)

        # Get WABA phone
        waba_phone = None
        if phone_id:
            waba_phone = await self.waba_phones.get_by_id(uuid.UUID(phone_id))
        else:
            waba_phone = await self._get_preferred_phone(contact)

        if not waba_phone:
            raise ValueError("No WABA Phone numbers found in DB.")

        template_id = None
        template_name = None
        if message_type == "template":
            from src.repositories.template import TemplateRepository

            template_repo = TemplateRepository(self.session)
            template = await template_repo.get_active_by_id(body)
            if template:
                template_id = template.id
                template_name = template.name
                body = template_name
            else:
                logger.error(f"Template {body} not found")
                raise ValueError(f"Template {body} not found")

        # Create message entity with scheduled_at
        message = await self.messages.create(
            waba_phone_id=waba_phone.id,
            contact_id=contact.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            message_type=message_type,
            body=body,
            template_id=template_id,
            reply_to_message_id=reply_to_message_id,
            scheduled_at=scheduled_at,
        )

        await self.session.commit()
        await self.session.refresh(message)

        logger.info(
            f"Created scheduled message {message.id} for {phone_number} at {scheduled_at}"
        )

        # Notify about scheduled message
        await self.notifier.notify_new_message(message, phone=contact.phone_number)

        return message

    # Supported MIME types by WhatsApp Business API
    SUPPORTED_MIME_TYPES = {
        # Audio
        "audio/aac",
        "audio/mp4",
        "audio/mpeg",
        "audio/amr",
        "audio/ogg",
        "audio/opus",
        # Documents
        "application/vnd.ms-powerpoint",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/pdf",
        "text/plain",
        "application/vnd.ms-excel",
        # Images
        "image/jpeg",
        "image/png",
        "image/webp",
        # Video
        "video/mp4",
        "video/3gpp",
    }

    async def send_media_message(
        self,
        phone_number: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        caption: str | None = None,
        phone_id: str | None = None,
    ) -> Message:
        """Send a media message with file upload."""
        # Step 1: Get or create contact
        contact = await self.contacts.get_or_create(phone_number)

        # Step 2: Get WABA phone
        waba_phone = await self._get_preferred_phone(contact, phone_id)
        if not waba_phone:
            raise ValueError("No eligible WABA Phone found")

        # Step 3: Determine media type
        media_type = self._get_media_type(mime_type)

        # Step 4: Create message entity FIRST (so we can record errors)
        message = await self.messages.create(
            waba_phone_id=waba_phone.id,
            contact_id=contact.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            message_type=media_type,
            body=caption,
        )

        await self.session.flush()
        await self.session.refresh(message)

        # Step 5: VALIDATION - Check MIME type
        # Якщо тип файлу не підтримується - ставимо статус FAILED, пишемо Warning і виходимо.
        if mime_type not in self.SUPPORTED_MIME_TYPES:
            error_message = (
                f"Unsupported file type '{mime_type}'. "
                f"WhatsApp only supports: audio, documents (PDF, DOC, XLS, PPT), "
                f"images (JPEG, PNG, WebP), and videos (MP4, 3GPP)."
            )
            message.status = MessageStatus.FAILED
            message.error_code = 100
            message.error_message = error_message

            self.session.add(message)
            await self.session.commit()

            # ВАЖЛИВО: Використовуємо warning замість error і return замість raise
            logger.warning(
                f"Media validation failed for {phone_number}. File: {filename}. Reason: {error_message}"
            )
            return message

        try:
            # Step 6: Upload to R2 (permanent storage)
            ext = mimetypes.guess_extension(mime_type) or ""
            r2_filename = f"{uuid.uuid4()}{ext}"
            r2_key = f"whatsapp/{media_type}s/{r2_filename}"

            logger.info(f"Uploading to R2: {r2_key}")
            await self.storage.upload_file(file_bytes, r2_key, mime_type)

            # Step 7: Upload to Meta (get media_id)
            logger.info(f"Uploading to Meta for phone {phone_number}")
            meta_media_id = await self.meta_client.upload_media(
                phone_id=waba_phone.phone_number_id,
                file_bytes=file_bytes,
                mime_type=mime_type,
                filename=filename,
            )

            logger.info(f"Meta media_id: {meta_media_id}")

            # Step 8: Save media file metadata
            await self.messages.add_media_file(
                message_id=message.id,
                meta_media_id=meta_media_id,
                file_name=filename,
                file_mime_type=mime_type,
                file_size=len(file_bytes),
                caption=caption,
                r2_key=r2_key,
                bucket_name=settings.R2_BUCKET_NAME,
            )

            # Step 9: Update contact
            contact.updated_at = message.created_at
            contact.last_message_at = message.created_at
            contact.last_message_id = message.id

            self.session.add(contact)

            # Step 10: Send via Meta API
            payload = MetaPayloadBuilder.build_media_message(
                to_phone=phone_number,
                media_type=media_type,
                media_id=meta_media_id,
                caption=caption,
            )

            result = await self.meta_client.send_message(
                waba_phone.phone_number_id, payload
            )

            wamid = result.get("messages", [{}])[0].get("id")

            if not wamid:
                raise Exception("No WAMID in Meta response")

            # Update message with WAMID
            message.wamid = wamid
            message.status = MessageStatus.SENT
            message.sent_at = get_utc_now()
            self.session.add(message)

            await self.session.commit()
            await self.session.refresh(message)

            logger.info(
                f"Media message sent to {phone_number}. WAMID: {wamid}")

            # Завантажуємо повідомлення з медіа файлами
            message_with_media = await self.messages.get_by_id(message.id)

            # Формуємо медіа файли для WebSocket
            media_files = []
            if message_with_media and message_with_media.media_files:
                for mf in message_with_media.media_files:
                    public_url = self.storage.get_public_url(mf.r2_key)
                    media_files.append(
                        {
                            "id": str(mf.id),
                            "file_name": mf.file_name,
                            "mime_type": mf.file_mime_type,
                            "file_size": mf.file_size,
                            "url": public_url,
                            "caption": mf.caption,
                        }
                    )

            # Notify
            await self.notifier.notify_new_message(
                message_with_media or message,
                media_files=media_files,
                phone=contact.phone_number,
            )

            await self.notifier.notify_message_status(
                message_id=message.id,
                wamid=wamid,
                status="sent",
                phone=contact.phone_number,
                sent_at=message.sent_at.isoformat() if message.sent_at else None,
            )

            return message

        except Exception as e:
            # Цей блок ловить тільки критичні помилки (мережа, API Meta)
            logger.debug(f"Failed to send media to {phone_number}: {e}")
            message.status = MessageStatus.FAILED

            # Parse error code and message from Meta API
            error_code = None
            error_message = str(e)

            # Try to extract error details from HTTP response
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"Meta API error response: {error_data}")

                    if "error" in error_data:
                        error_info = error_data["error"]
                        error_code = error_info.get("code")
                        error_message = error_info.get("message", str(e))

                        # Log additional error details if available
                        if "error_subcode" in error_info:
                            logger.debug(
                                f"Error subcode: {error_info['error_subcode']}"
                            )
                        if "error_user_title" in error_info:
                            logger.debug(
                                f"Error title: {error_info['error_user_title']}"
                            )
                        if "error_user_msg" in error_info:
                            logger.debug(
                                f"Error user message: {error_info['error_user_msg']}"
                            )
                except Exception as parse_error:
                    logger.warning(
                        f"Failed to parse error response: {parse_error}")

            message.error_code = error_code
            message.error_message = error_message[:500] if error_message else None

            self.session.add(message)
            await self.session.commit()

            # Для системних помилок ми все ще кидаємо exception,
            # щоб система могла спробувати повторити (якщо налаштовано retry) або залогувати як баг
            raise

    async def send_reaction(
        self, contact: Contact, message_id: uuid.UUID, emoji: str = ""
    ):
        """Send (or remove) a reaction to a specific message."""
        target_message = await self.messages.get_by_id(message_id)
        if not target_message or not target_message.wamid:
            logger.error(
                f"Cannot react: Message {message_id} not found or has no WAMID"
            )
            return

        if target_message.waba_phone_id:
            waba_phone = await self.waba_phones.get_by_id(target_message.waba_phone_id)
        else:
            waba_phone = None

        if not waba_phone:
            logger.error("Cannot react: No WABA phone found")
            return

        payload = MetaPayloadBuilder.build_reaction_message(
            to_phone=contact.phone_number,
            target_wamid=target_message.wamid,
            emoji=emoji,
        )

        try:
            await self.meta_client.send_message(waba_phone.phone_number_id, payload)

            target_message.reaction = emoji
            self.session.add(target_message)
            await self.session.commit()

            logger.info(f"Sent reaction '{emoji}' to {contact.phone_number}")

            await self.notifier.notify_message_reaction(
                message_id=target_message.id, reaction=emoji, phone=contact.phone_number
            )

        except Exception as e:
            logger.error(f"Failed to send reaction: {e}")
            raise

    async def send_to_contact(
        self,
        contact: Contact,
        message_type: str,
        body: str,
        template_id: uuid.UUID | None = None,
        template_name: str | None = None,
        template_language_code: str | None = None,
        template_parameters: list[dict] | None = None,
        is_campaign: bool = False,
        reply_to_message_id: uuid.UUID | None = None,
        phone_id: str | None = None,
        existing_message: Message | None = None,
    ) -> Message:
        """
        Send message to a contact.
        IMPORTANT: This method does NOT commit.
        The caller must commit the transaction.
        """
        waba_phone = None
        if phone_id:
            waba_phone = await self.waba_phones.get_by_id(uuid.UUID(phone_id))
        else:
            waba_phone = await self._get_preferred_phone(contact)

        if not waba_phone:
            raise ValueError("No WABA Phone numbers found in DB.")

        context_wamid = None
        if reply_to_message_id:
            parent_msg = await self.messages.get_by_id(reply_to_message_id)
            if parent_msg:
                context_wamid = parent_msg.wamid
            else:
                logger.warning(
                    f"Reply target message {reply_to_message_id} not found")

        # Render template body if this is a template message
        message_body = body
        if message_type == "template" and template_id:
            from src.repositories.template import TemplateRepository
            from src.utils.template_renderer import render_template_for_message

            # Load template to get components
            template_repo = TemplateRepository(self.session)
            template = await template_repo.get_by_id(template_id)

            if template and template.components:
                # Extract parameter values from template_parameters
                param_values = []
                if template_parameters:
                    for param in template_parameters:
                        if param.get("type") == "text":
                            param_values.append(param.get("text", ""))

                # Render the full message text
                try:
                    message_body = render_template_for_message(
                        template.components,
                        param_values if param_values else None
                    )
                except Exception as render_error:
                    logger.warning(
                        f"Failed to render template {template_id}: {render_error}")
                    # Fall back to template name if rendering fails
                    message_body = template_name or "Template message"
            else:
                # No template found or no components
                message_body = template_name or "Template message"

        # Use existing message or create new one
        if existing_message:
            message = existing_message
            # Ensure critical fields are set/updated if needed
            if not message.waba_phone_id:
                message.waba_phone_id = waba_phone.id
            # Update body with rendered text
            message.body = message_body
        else:
            message = await self.messages.create(
                waba_phone_id=waba_phone.id,
                contact_id=contact.id,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.PENDING,
                message_type=message_type,
                body=message_body,
                template_id=template_id,
                reply_to_message_id=reply_to_message_id,
            )

        await self.session.flush()
        await self.session.refresh(message)

        contact.updated_at = message.created_at
        contact.last_message_at = message.created_at
        contact.last_message_id = message.id

        self.session.add(contact)

        if not is_campaign:
            await self.notifier.notify_new_message(message, phone=contact.phone_number)

            # Use the rendered message body for preview
            preview_body = message_body or (
                template_name or f"Sent {message_type}")

            await self.notifier._publish(
                {
                    "event": "contact_updated",
                    "data": {
                        "id": str(contact.id),
                        "phone_number": contact.phone_number,
                        "unread_count": contact.unread_count,
                        "last_message_at": contact.last_message_at.isoformat(),
                        "last_message_body": preview_body,
                        "last_message_type": message_type,
                        "last_message_status": "pending",
                        "last_message_direction": "outbound",
                    },
                    "timestamp": message.created_at.isoformat(),
                }
            )

        try:
            # Send to Meta
            payload = self._build_payload(
                to_phone=contact.phone_number,
                message_type=message_type,
                body=body,
                template_name=template_name,
                template_language_code=template_language_code,
                template_parameters=template_parameters,
                context_wamid=context_wamid,
            )

            result = await self.meta_client.send_message(
                waba_phone.phone_number_id, payload, idempotency_key=str(
                    message.id)
            )
            wamid = result.get("messages", [{}])[0].get("id")

            if not wamid:
                raise Exception("No WAMID in Meta response")

            # Update message with WAMID
            message.wamid = wamid
            message.status = MessageStatus.SENT
            message.sent_at = get_utc_now()
            self.session.add(message)

            logger.info(
                f"Message sent to {contact.phone_number}. WAMID: {wamid}")

            if not is_campaign:
                await self.notifier.notify_message_status(
                    message_id=message.id,
                    wamid=wamid,
                    status="sent",
                    phone=contact.phone_number,
                    sent_at=message.sent_at.isoformat() if message.sent_at else None,
                )

            return message

        except Exception as e:
            logger.warning(f"Failed to send to {contact.phone_number}: {e}")
            message.status = MessageStatus.FAILED

            # Parse error code and message from Meta API
            error_code = None
            error_message = str(e)

            # Try to extract error details from HTTP response
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.warning(f"Meta API error response: {error_data}")

                    if "error" in error_data:
                        error_info = error_data["error"]
                        error_code = error_info.get("code")
                        error_message = error_info.get("message", str(e))

                        # Log additional error details if available
                        if "error_subcode" in error_info:
                            logger.debug(
                                f"Error subcode: {error_info['error_subcode']}"
                            )
                        if "error_user_title" in error_info:
                            logger.debug(
                                f"Error title: {error_info['error_user_title']}"
                            )
                        if "error_user_msg" in error_info:
                            logger.debug(
                                f"Error user message: {error_info['error_user_msg']}"
                            )
                except Exception as parse_error:
                    logger.warning(
                        f"Failed to parse error response: {parse_error}")

            message.error_code = error_code
            message.error_message = error_message[:500] if error_message else None

            self.session.add(message)

            # For campaign messages, return the failed message instead of raising
            # This allows the campaign executor to handle the failure gracefully
            if is_campaign:
                logger.info(
                    f"Returning failed campaign message for {contact.phone_number}")
                return message

            # For non-campaign messages, raise to maintain backward compatibility
            raise

    def _get_media_type(self, mime_type: str) -> str:
        """Determine WhatsApp media type from MIME type."""
        if mime_type.startswith("image/"):
            if "webp" in mime_type:
                return "sticker"
            return "image"
        elif mime_type.startswith("video/"):
            return "video"
        elif mime_type.startswith("audio/"):
            if "ogg" in mime_type or "opus" in mime_type:
                return "voice"
            return "audio"
        else:
            return "document"

    def _build_payload(
        self,
        to_phone: str,
        message_type: str,
        body: str,
        template_name: str | None,
        template_language_code: str | None = None,
        template_parameters: list[dict] | None = None,
        context_wamid: str | None = None,
    ) -> dict:
        """Build WhatsApp API payload using MetaPayloadBuilder."""
        if message_type == "text":
            return MetaPayloadBuilder.build_text_message(
                to_phone=to_phone,
                body=body,
                context_wamid=context_wamid,
            )
        elif message_type == "template":
            if not template_name:
                raise ValueError("Template name required")
            return MetaPayloadBuilder.build_template_message(
                to_phone=to_phone,
                template_name=template_name,
                language_code=template_language_code or "en_US",
                parameters=template_parameters,
                context_wamid=context_wamid,
            )
        else:
            raise ValueError(f"Unsupported message type: {message_type}")

    async def _get_preferred_phone(self, contact: Contact, phone_id: str | None = None):
        """Get the preferred phone number for a contact."""
        if phone_id:
            try:
                p_uuid = uuid.UUID(str(phone_id))
                phone = await self.waba_phones.get_by_id(p_uuid)
                if phone:
                    return phone
            except ValueError:
                logger.warning(f"Invalid phone_id provided: {phone_id}")

        if contact.last_message_id:
            last_msg = await self.messages.get_by_id(contact.last_message_id)
            if last_msg and last_msg.waba_phone_id:
                phone = await self.waba_phones.get_by_id(last_msg.waba_phone_id)
                if phone:
                    return phone

        return None
