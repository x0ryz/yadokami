import mimetypes
import uuid

from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.clients.meta import MetaClient
from src.core.config import settings
from src.models import (
    Contact,
    MediaFile,
    Message,
    MessageDirection,
    MessageStatus,
    WabaPhoneNumber,
)
from src.schemas import WhatsAppMessage
from src.services.storage import StorageService


class WhatsAppService:
    def __init__(self, session: AsyncSession, meta_client: MetaClient):
        self.session = session
        self.meta_client = meta_client

    async def send_outbound_message(self, message: WhatsAppMessage):
        # Find existing contact or create a new one if it doesn't exist
        stmt_contact = select(Contact).where(
            Contact.phone_number == message.phone_number
        )
        contact = (await self.session.exec(stmt_contact)).first()

        if not contact:
            contact = Contact(phone_number=message.phone_number)
            self.session.add(contact)
            await self.session.commit()
            await self.session.refresh(contact)

        stmt_phone = select(WabaPhoneNumber)
        waba_phone = (await self.session.exec(stmt_phone)).first()

        if not waba_phone:
            logger.error("No WABA Phone numbers found in DB.")
            return

        db_message = Message(
            waba_phone_id=waba_phone.id,
            contact_id=contact.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            body=message.body,
        )

        self.session.add(db_message)
        await self.session.commit()
        await self.session.refresh(db_message)

        try:
            # Construct specific payload structure depending on message type
            if message.type == "text":
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": message.phone_number,
                    "type": "text",
                    "text": {"body": message.body},
                }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": message.phone_number,
                    "type": "template",
                    "template": {
                        "name": message.body,
                        "language": {"code": "en_US"},
                    },
                }

            result = await self.meta_client.send_message(
                waba_phone.phone_number_id, payload
            )

            # Safely extract WAMID using a defensive approach to handle potential API format changes
            wamid = result.get("messages", [{}])[0].get("id")

            if wamid:
                db_message.wamid = wamid
                db_message.status = MessageStatus.SENT
                self.session.add(db_message)
                await self.session.commit()
                logger.success(
                    f"Message sent to {message.phone_number}. WAMID: {wamid}"
                )

        except Exception as e:
            logger.exception(f"Failed to send message to {message.phone_number}")
            db_message.status = MessageStatus.FAILED
            self.session.add(db_message)
            await self.session.commit()

    async def process_webhook(self, payload: dict):
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                if "statuses" in value:
                    await self._handle_statuses(value["statuses"])

                if "messages" in value:
                    await self._handle_incoming_messages(value)

    def _get_status_weight(self, status: MessageStatus) -> int:
        weights = {
            MessageStatus.PENDING: 0,
            MessageStatus.SENT: 1,
            MessageStatus.DELIVERED: 2,
            MessageStatus.READ: 3,
            MessageStatus.FAILED: 4,
        }
        return weights.get(status, -1)

    async def _handle_statuses(self, statuses: list):
        status_map = {
            "sent": MessageStatus.SENT,
            "delivered": MessageStatus.DELIVERED,
            "read": MessageStatus.READ,
            "failed": MessageStatus.FAILED,
        }

        for status in statuses:
            wamid = status.get("id")
            new_status_str = status.get("status")
            new_status = status_map.get(new_status_str)

            if wamid and new_status:
                stmt = select(Message).where(Message.wamid == wamid)
                db_message = (await self.session.exec(stmt)).first()

                if db_message:
                    current_weight = self._get_status_weight(db_message.status)
                    new_weight = self._get_status_weight(new_status)

                    if new_weight > current_weight:
                        old_status = db_message.status
                        db_message.status = new_status
                        self.session.add(db_message)
                        logger.info(
                            f"Updated status for {wamid}: {old_status} -> {new_status}"
                        )
                    else:
                        logger.debug(
                            f"Ignored outdated status {new_status} for {wamid} "
                            f"(current: {db_message.status})"
                        )

        await self.session.commit()

    async def _handle_incoming_messages(self, value: dict):
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")

        stmt_phone = select(WabaPhoneNumber).where(
            WabaPhoneNumber.phone_number_id == phone_number_id
        )
        waba_phone = (await self.session.exec(stmt_phone)).first()

        if not waba_phone:
            logger.warning(f"Webhook for unknown phone ID: {phone_number_id}")
            return

        storage_service = StorageService()

        for msg in value.get("messages", []):
            wamid = msg.get("id")
            from_phone = msg.get("from")

            stmt_dup = select(Message).where(Message.wamid == wamid)
            if (await self.session.exec(stmt_dup)).first():
                logger.info(f"Message {wamid} already processed")
                continue

            stmt_contact = select(Contact).where(Contact.phone_number == from_phone)
            contact = (await self.session.exec(stmt_contact)).first()
            if not contact:
                contact = Contact(
                    phone_number=from_phone,
                    name=msg.get("profile", {}).get("name"),
                )
                self.session.add(contact)
                await self.session.commit()
                await self.session.refresh(contact)

            parsed_data = self._parse_message_data(msg)

            new_msg = Message(
                waba_phone_id=waba_phone.id,
                contact_id=contact.id,
                direction=MessageDirection.INBOUND,
                status=MessageStatus.RECEIVED,
                wamid=wamid,
                message_type=parsed_data["type"],
                body=parsed_data["body"],
            )
            self.session.add(new_msg)
            await self.session.commit()
            await self.session.refresh(new_msg)
            if parsed_data["media_id"]:
                await self._process_media_attachment(
                    new_msg, parsed_data, msg, storage_service
                )
            logger.info(f"Saved {parsed_data['type']} message from {from_phone}")

    def _parse_message_data(self, msg: dict) -> dict:
        """Return structures: {type, body, media_id, caption}"""
        msg_type = msg.get("type")
        data = msg.get(msg_type, {})
        result = {"type": msg_type, "body": None, "media_id": None, "caption": None}

        match msg_type:
            case "text":
                result["body"] = data.get("body")

            case "image" | "document" | "video":
                result["media_id"] = data.get("id")
                result["caption"] = data.get("caption")

            case "voice" | "audio" | "sticker":
                result["media_id"] = data.get("id")

            case _:
                pass

        return result

    async def _process_media_attachment(
        self,
        db_message: Message,
        parsed_data: dict,
        raw_msg: dict,
        storage: StorageService,
    ):
        try:
            media_id = parsed_data["media_id"]

            media_url = await self.meta_client.get_media_url(media_id)
            file_content = await self.meta_client.download_media_file(media_url)

            msg_type = parsed_data["type"]
            mime_type = raw_msg.get(msg_type, {}).get(
                "mime_type", "application/octet-stream"
            )
            ext = mimetypes.guess_extension(mime_type) or ".bin"

            filename = f"{uuid.uuid4()}{ext}"
            r2_key = f"whatsapp/{msg_type}s/{filename}"

            await storage.upload_file(file_content, r2_key, mime_type)

            media_entry = MediaFile(
                message_id=db_message.id,
                meta_media_id=media_id,
                file_name=filename,
                file_mime_type=mime_type,
                file_size=len(file_content),
                caption=parsed_data["caption"],
                r2_key=r2_key,
                bucket_name=settings.R2_BUCKET_NAME,
            )
            self.session.add(media_entry)
            await self.session.commit()

            logger.info(f"Saved media to R2 and linked to message: {r2_key}")

        except Exception as e:
            logger.error(f"Media processing failed for msg {db_message.id}: {e}")
