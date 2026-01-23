import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.broker import broker
from src.models import MessageDirection, MessageStatus, get_utc_now
from src.repositories.contact import ContactRepository
from src.repositories.message import MessageRepository
from src.repositories.waba import WabaPhoneRepository
from src.schemas import MetaMessage
from src.services.campaign.tracker import CampaignTrackerService
from src.services.media.service import MediaService
from src.services.messaging.parsers import extract_message_body, prepare_media_task
from src.services.notifications.service import NotificationService


class IncomingMessageHandler:
    """Orchestrates incoming message processing workflow."""

    def __init__(
        self,
        session: AsyncSession,
        media_service: MediaService,
        notifier: NotificationService,
    ):
        self.session = session
        self.media_service = media_service
        self.notifier = notifier

        # Services & Repositories
        self.campaign_tracker = CampaignTrackerService(session)
        self.contacts = ContactRepository(session)
        self.messages = MessageRepository(session)
        self.waba_phones = WabaPhoneRepository(session)

    async def handle(self, messages: list[MetaMessage], phone_number_id: str):
        """Main entry point."""
        waba_phone = await self.waba_phones.get_by_phone_id(phone_number_id)
        if not waba_phone:
            logger.warning(f"Unknown phone ID: {phone_number_id}")
            return

        for msg in messages:
            if msg.type == "reaction" and msg.reaction:
                await self._handle_reaction(msg)
            else:
                await self._handle_message(msg, waba_phone.id)

    async def _handle_message(self, msg: MetaMessage, waba_id: uuid.UUID):
        """Processes a single standard message."""
        # 1. Deduplication
        if await self.messages.exists_by_wamid(msg.id):
            logger.info(f"Message {msg.id} deduplicated")
            return

        # 2. Update Contact Activity
        contact = await self.contacts.update_activity(msg.from_)

        # 3. Campaign Tracker
        await self.campaign_tracker.handle_reply(contact.id)

        # 4. Create Message in DB
        body = extract_message_body(msg)
        reply_to_id = await self.messages.resolve_reply_id(msg, contact.id)

        new_msg = await self.messages.create(
            waba_phone_id=waba_id,
            contact_id=contact.id,
            direction=MessageDirection.INBOUND,
            status=MessageStatus.RECEIVED,
            wamid=msg.id,
            message_type=msg.type,
            body=body,
            reply_to_message_id=reply_to_id,
        )

        # !!! ВАЖЛИВО: Генеруємо ID перед тим як використовувати його далі !!!
        await self.session.flush()

        # Оновлюємо посилання на останнє повідомлення
        contact.last_message_id = new_msg.id
        self.contacts.add(contact)

        # 5. Prepare Side Effects (тепер new_msg.id точно існує)
        media_task = prepare_media_task(msg, new_msg.id)

        # 6. Commit Transaction
        await self.session.commit()

        # 7. Dispatch Side Effects (After Commit)
        await self._dispatch_side_effects(new_msg, contact, media_task)

    async def _handle_reaction(self, msg: MetaMessage):
        """Processes reaction events."""
        target_msg = await self.messages.get_by_wamid(msg.reaction.message_id)

        if not target_msg:
            contact = await self.contacts.get_or_create(msg.from_)
            target_msg = await self.messages._fuzzy_find_message(
                contact.id, msg.reaction.message_id
            )

        if not target_msg:
            logger.warning(
                f"Target message {msg.reaction.message_id} for reaction not found."
            )
            return

        target_msg.reaction = msg.reaction.emoji
        self.messages.add(target_msg)
        logger.info(
            f"Updated reaction for msg {target_msg.id}: {msg.reaction.emoji}")

        await self.session.commit()

        await self.notifier.notify_message_reaction(
            message_id=target_msg.id,
            reaction=msg.reaction.emoji,
            phone=msg.from_,
        )

    async def _dispatch_side_effects(self, new_msg, contact, media_task: dict | None):
        """Handles NATS publishing and WebSocket notifications."""
        if media_task:
            await broker.publish(media_task, subject="media.download")
            logger.info(
                f"Queued media download for msg {media_task['message_id']}")

        await self.notifier.notify_new_message(
            new_msg,
            phone=contact.phone_number,
            media_files=[],
        )

        # Notify about contact session update (for 24h window tracking)
        await self.notifier.notify_contact_session_update(
            contact_id=contact.id,
            phone=contact.phone_number,
            last_message_at=contact.last_message_at or get_utc_now(),
            last_incoming_message_at=contact.last_incoming_message_at,
        )

        preview_body = new_msg.body if new_msg.body else f"Sent {new_msg.message_type}"
        await self.notifier._publish(
            {
                "event": "contact_updated",
                "data": {
                    "id": str(contact.id),
                    "phone_number": contact.phone_number,
                    "unread_count": contact.unread_count,
                    "last_message_at": contact.last_message_at.isoformat(),
                    "last_message_body": preview_body,
                    "last_message_type": new_msg.message_type,
                    "last_message_status": "received",
                },
                "timestamp": get_utc_now().isoformat(),
            }
        )
