import mimetypes
import uuid

from loguru import logger
from src.clients.meta import MetaClient
from src.core.config import settings
from src.core.uow import UnitOfWork
from src.models import Contact, Message, MessageDirection, MessageStatus
from src.schemas import WhatsAppMessage
from src.services.media.storage import StorageService
from src.services.notifications.service import NotificationService


class MessageSenderService:
    """
    Message sending service.

    IMPORTANT: This service manages transactions.
    Each public method commits its changes.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        meta_client: MetaClient,
        notifier: NotificationService,
        storage: StorageService | None = None,
    ):
        self.uow = uow
        self.meta_client = meta_client
        self.notifier = notifier
        self.storage = storage or StorageService()

    async def send_manual_message(self, message: WhatsAppMessage):
        """
        Send a manual message (from API).
        This method manages its own transaction.
        """
        async with self.uow:
            contact = await self.uow.contacts.get_or_create(message.phone_number)

            template_id = None
            template_name = None

            if message.type == "template":
                template = await self.uow.templates.get_active_by_id(message.body)
                if template:
                    template_id = template.id
                    template_name = template.name
                else:
                    logger.error(f"Template {message.body} not found")
                    return

            await self._send_and_commit(
                contact=contact,
                message_type=message.type,
                body=message.body,
                template_id=template_id,
                template_name=template_name,
                is_campaign=False,
                reply_to_message_id=message.reply_to_message_id,
            )

    async def send_media_message(
        self,
        phone_number: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        caption: str | None = None,
    ) -> Message:
        """
        Send a media message with file upload.

        Process:
        1. Get or create contact
        2. Upload file to R2 (permanent storage)
        3. Upload file to Meta (get temporary media_id)
        4. Create message in DB
        5. Send message via Meta API
        6. Link media file to message

        Args:
            phone_number: Recipient phone number
            file_bytes: Binary file content
            filename: Original filename
            mime_type: File MIME type
            caption: Optional caption text

        Returns:
            Message: Created message object

        Raises:
            Exception: If any step fails
        """
        async with self.uow:
            # Step 1: Get or create contact
            contact = await self.uow.contacts.get_or_create(phone_number)

            # Step 2: Get WABA phone
            waba_phone = await self.uow.waba.get_default_phone()
            if not waba_phone:
                raise ValueError("No WABA Phone numbers found in DB.")

            # Step 3: Upload to R2 (permanent storage)
            media_type = self._get_media_type(mime_type)
            ext = mimetypes.guess_extension(mime_type) or ""
            r2_filename = f"{uuid.uuid4()}{ext}"
            r2_key = f"whatsapp/{media_type}s/{r2_filename}"

            logger.info(f"Uploading to R2: {r2_key}")
            await self.storage.upload_file(file_bytes, r2_key, mime_type)

            # Step 4: Upload to Meta (get media_id)
            logger.info(f"Uploading to Meta for phone {phone_number}")
            meta_media_id = await self.meta_client.upload_media(
                phone_id=waba_phone.phone_number_id,
                file_bytes=file_bytes,
                mime_type=mime_type,
                filename=filename,
            )

            logger.info(f"Meta media_id: {meta_media_id}")

            # Step 5: Create message entity
            message = await self.uow.messages.create(
                waba_phone_id=waba_phone.id,
                contact_id=contact.id,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.PENDING,
                message_type=media_type,
                body=caption,
            )

            await self.uow.session.flush()
            await self.uow.session.refresh(message)

            # Step 6: Save media file metadata
            await self.uow.messages.add_media_file(
                message_id=message.id,
                meta_media_id=meta_media_id,
                file_name=filename,
                file_mime_type=mime_type,
                file_size=len(file_bytes),
                caption=caption,
                r2_key=r2_key,
                bucket_name=settings.R2_BUCKET_NAME,
            )

            # Step 7: Update contact
            contact.updated_at = message.created_at
            contact.last_message_at = message.created_at
            contact.last_message_id = message.id
            self.uow.session.add(contact)

            # Step 8: Send via Meta API
            try:
                payload = self._build_media_payload(
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
                self.uow.session.add(message)

                await self.uow.commit()
                await self.uow.session.refresh(message)

                logger.info(f"Media message sent to {phone_number}. WAMID: {wamid}")

                # Notify
                await self.notifier.notify_new_message(
                    message, phone=contact.phone_number
                )

                await self.notifier.notify_message_status(
                    message_id=message.id,
                    wamid=wamid,
                    status="sent",
                    phone=contact.phone_number,
                )

                return message

            except Exception as e:
                logger.error(f"Failed to send media to {phone_number}: {e}")
                message.status = MessageStatus.FAILED
                self.uow.session.add(message)
                await self.uow.commit()
                raise

    async def send_reaction(
        self, contact: Contact, message_id: uuid.UUID, emoji: str = ""
    ):
        """
        Send (or remove) a reaction to a specific message.
        To remove a reaction, pass an empty string as emoji.
        """
        target_message = await self.uow.messages.get_by_id(message_id)
        if not target_message or not target_message.wamid:
            logger.error(
                f"Cannot react: Message {message_id} not found or has no WAMID"
            )
            return

        waba_phone = await self.uow.waba.get_default_phone()

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": contact.phone_number,
            "type": "reaction",
            "reaction": {"message_id": target_message.wamid, "emoji": emoji},
        }

        try:
            await self.meta_client.send_message(waba_phone.phone_number_id, payload)

            target_message.reaction = emoji
            self.uow.session.add(target_message)
            await self.uow.commit()

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
        is_campaign: bool = False,
        reply_to_message_id: uuid.UUID | None = None,
    ) -> Message:
        """
        Send message to a contact.
        IMPORTANT: This method does NOT commit.
        The caller must commit the transaction.
        """
        waba_phone = await self.uow.waba.get_default_phone()
        if not waba_phone:
            raise ValueError("No WABA Phone numbers found in DB.")

        context_wamid = None
        if reply_to_message_id:
            parent_msg = await self.uow.messages.get_by_id(reply_to_message_id)
            if parent_msg:
                context_wamid = parent_msg.wamid
            else:
                logger.warning(f"Reply target message {reply_to_message_id} not found")

        # Create message entity
        message = await self.uow.messages.create(
            waba_phone_id=waba_phone.id,
            contact_id=contact.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            message_type=message_type,
            body=body if message_type == "text" else template_name,
            template_id=template_id,
            reply_to_message_id=reply_to_message_id,
        )

        await self.uow.session.flush()
        await self.uow.session.refresh(message)

        contact.updated_at = message.created_at
        contact.last_message_at = message.created_at
        contact.last_message_id = message.id
        self.uow.session.add(contact)

        if not is_campaign:
            await self.notifier.notify_new_message(message, phone=contact.phone_number)

            preview_body = (
                body
                if message_type == "text"
                else (template_name or f"Sent {message_type}")
            )

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
                context_wamid=context_wamid,
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
            self.uow.session.add(message)

            logger.info(f"Message sent to {contact.phone_number}. WAMID: {wamid}")

            if not is_campaign:
                await self.notifier.notify_message_status(
                    message_id=message.id,
                    wamid=wamid,
                    status="sent",
                    phone=contact.phone_number,
                )

            return message

        except Exception as e:
            logger.error(f"Failed to send to {contact.phone_number}: {e}")
            message.status = MessageStatus.FAILED
            self.uow.session.add(message)
            raise

    async def _send_and_commit(
        self,
        contact: Contact,
        message_type: str,
        body: str,
        template_id: uuid.UUID | None,
        template_name: str | None,
        is_campaign: bool,
        reply_to_message_id: uuid.UUID | None = None,
    ):
        try:
            await self.send_to_contact(
                contact=contact,
                message_type=message_type,
                body=body,
                template_id=template_id,
                template_name=template_name,
                is_campaign=is_campaign,
                reply_to_message_id=reply_to_message_id,
            )
            await self.uow.commit()
        except Exception:
            await self.uow.commit()
            raise

    def _get_media_type(self, mime_type: str) -> str:
        """
        Determine WhatsApp media type from MIME type.

        Returns: image, video, audio, document, sticker
        """
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

    def _build_media_payload(
        self,
        to_phone: str,
        media_type: str,
        media_id: str,
        caption: str | None = None,
    ) -> dict:
        """Build WhatsApp API payload for media message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": media_type,
            media_type: {
                "id": media_id,
            },
        }

        # Add caption if provided and supported
        if caption and media_type in ["image", "video", "document"]:
            payload[media_type]["caption"] = caption

        return payload

    def _build_payload(
        self,
        to_phone: str,
        message_type: str,
        body: str,
        template_name: str | None,
        context_wamid: str | None = None,
    ) -> dict:
        """Build WhatsApp API payload."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": message_type,
        }
        if context_wamid:
            payload["context"] = {"message_id": context_wamid}
        if message_type == "text":
            payload["text"] = {"body": body}
        elif message_type == "template":
            if not template_name:
                raise ValueError("Template name required")
            payload["template"] = {
                "name": template_name,
                "language": {"code": "en_US"},
            }
        return payload
