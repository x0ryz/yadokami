import base64

from loguru import logger
from src.core.uow import UnitOfWork
from src.models import MessageDirection, MessageStatus, get_utc_now
from src.schemas import MetaMessage, MetaStatus, MetaWebhookPayload
from src.services.media.service import MediaService
from src.services.notifications.service import NotificationService


class MessageProcessorService:
    def __init__(
        self,
        uow: UnitOfWork,
        media_service: MediaService,
        notifier: NotificationService,
    ):
        self.uow = uow
        self.media = media_service
        self.notifier = notifier

    async def process_webhook(self, webhook: MetaWebhookPayload):
        """Маршрутизація подій вебхука"""
        for entry in webhook.entry:
            for change in entry.changes:
                value = change.value

                if value.statuses:
                    await self._handle_statuses(value.statuses)

                if value.messages:
                    phone_id = value.metadata.get("phone_number_id")
                    await self._handle_messages(value.messages, phone_id)

    async def _handle_statuses(self, statuses: list[MetaStatus]):
        status_map = {
            "sent": MessageStatus.SENT,
            "delivered": MessageStatus.DELIVERED,
            "read": MessageStatus.READ,
            "failed": MessageStatus.FAILED,
        }

        async with self.uow:
            for status in statuses:
                new_status = status_map.get(status.status)
                if not new_status:
                    continue

                db_message = await self.uow.messages.get_by_wamid(status.id)
                if not db_message:
                    continue

                if self._is_newer_status(db_message.status, new_status):
                    db_message.status = new_status
                    self.uow.session.add(db_message)

                    await self.notifier.notify_message_status(
                        message_id=db_message.id,
                        wamid=status.id,
                        status=status.status,
                        phone=db_message.contact.phone_number
                        if db_message.contact
                        else None,
                    )

            await self.uow.commit()

    async def _handle_messages(self, messages: list[MetaMessage], phone_number_id: str):
        from src.worker import handle_media_download_task

        waba_phone_db_id = None
        async with self.uow:
            waba_phone = await self.uow.waba.get_by_phone_id(phone_number_id)
            if waba_phone:
                waba_phone_db_id = waba_phone.id

        if not waba_phone_db_id:
            logger.warning(f"Unknown phone ID: {phone_number_id}")
            return

        for msg in messages:
            if msg.type == "reaction" and msg.reaction:
                async with self.uow:
                    target_msg = await self.uow.messages.get_by_wamid(
                        msg.reaction.message_id
                    )

                    if not target_msg:
                        target_msg = await self._fuzzy_find_message(
                            msg.from_, msg.reaction.message_id
                        )

                    if target_msg:
                        target_msg.reaction = msg.reaction.emoji
                        self.uow.session.add(target_msg)
                        logger.info(
                            f"Updated reaction for msg {target_msg.id}: {msg.reaction.emoji}"
                        )
                        await self.notifier.notify_message_reaction(
                            message_id=target_msg.id,
                            reaction=msg.reaction.emoji,
                            phone=msg.from_,
                        )
                        await self.uow.commit()
                    else:
                        logger.warning(
                            f"Target message {msg.reaction.message_id} not found anywhere."
                        )
                continue

            async with self.uow:
                if await self.uow.messages.get_by_wamid(msg.id):
                    logger.info(f"Message {msg.id} deduplicated")
                    continue

                contact = await self.uow.contacts.get_or_create(msg.from_)

                contact.unread_count += 1
                contact.updated_at = get_utc_now()

                body = None
                if msg.type == "text":
                    body = msg.text.body
                elif msg.type == "interactive":
                    interactive = msg.interactive
                    if interactive.type == "button_reply":
                        body = interactive.button_reply.title
                    elif interactive.type == "list_reply":
                        body = interactive.list_reply.title
                elif msg.type == "location":
                    loc = msg.location
                    body = f"Location: {loc.name or ''} {loc.address or ''} ({loc.latitude}, {loc.longitude})".strip()
                elif msg.type == "contacts" and msg.contacts:
                    c = msg.contacts[0]
                    name = c.name.formatted_name if c.name else "Unknown"
                    phone = c.phones[0].phone if c.phones else "No phone"
                    body = f"Contact: {name} ({phone})"
                elif hasattr(msg, msg.type):
                    media_obj = getattr(msg, msg.type)
                    if hasattr(media_obj, "caption"):
                        body = media_obj.caption

                reply_to_uuid = None

                if msg.context and msg.context.id:
                    ctx_wamid = msg.context.id
                    parent_msg = await self.uow.messages.get_by_wamid(ctx_wamid)

                    if not parent_msg:
                        logger.info(
                            f"Context parent {ctx_wamid} not found directly. Trying fuzzy match."
                        )
                        parent_msg = await self._fuzzy_find_message(
                            msg.from_, ctx_wamid
                        )

                    if parent_msg:
                        reply_to_uuid = parent_msg.id
                        logger.info(
                            f"Linked reply to parent message UUID: {parent_msg.id}"
                        )
                    else:
                        logger.warning(
                            f"Parent message with WAMID {ctx_wamid} not found. Reply link will be null."
                        )

                new_msg = await self.uow.messages.create(
                    waba_phone_id=waba_phone_db_id,
                    contact_id=contact.id,
                    direction=MessageDirection.INBOUND,
                    status=MessageStatus.RECEIVED,
                    wamid=msg.id,
                    message_type=msg.type,
                    body=body,
                    reply_to_message_id=reply_to_uuid,
                )

                await self.uow.session.flush()

                contact.last_message_id = new_msg.id
                contact.last_message_at = new_msg.created_at
                self.uow.session.add(contact)

                if msg.type in [
                    "image",
                    "video",
                    "document",
                    "audio",
                    "voice",
                    "sticker",
                ]:
                    media_meta = getattr(msg, msg.type, None)

                    if media_meta:
                        await handle_media_download_task.kiq(
                            message_id=new_msg.id,
                            meta_media_id=media_meta.id,
                            media_type=msg.type,
                            mime_type=media_meta.mime_type
                            or "application/octet-stream",
                            caption=media_meta.caption,
                        )
                        logger.info(f"Queued media download for msg {new_msg.id}")

                await self.uow.commit()

                media_dtos = []

                await self.notifier.notify_new_message(
                    new_msg,
                    phone=contact.phone_number,
                    media_files=media_dtos,
                )

                preview_body = body if body else f"Sent {msg.type}"

                await self.notifier._publish(
                    {
                        "event": "contact_updated",
                        "data": {
                            "id": str(contact.id),
                            "phone_number": contact.phone_number,
                            "unread_count": contact.unread_count,
                            "last_message_at": contact.last_message_at.isoformat(),
                            "last_message_body": preview_body,
                            "last_message_type": msg.type,
                            "last_message_status": "received",
                        },
                        "timestamp": get_utc_now().isoformat(),
                    }
                )

    def _is_newer_status(self, old: MessageStatus, new: MessageStatus) -> bool:
        weights = {
            MessageStatus.PENDING: 0,
            MessageStatus.SENT: 1,
            MessageStatus.DELIVERED: 2,
            MessageStatus.READ: 3,
            MessageStatus.FAILED: 4,
        }
        return weights.get(new, -1) > weights.get(old, -1)

    async def _fuzzy_find_message(self, phone_number: str, target_wamid: str):
        """Шукає повідомлення за останніми 8 байтами ID (ігнорує префікс)."""
        try:
            contact = await self.uow.contacts.get_or_create(phone_number)
            # Беремо останні 50 повідомлень
            last_msgs = await self.uow.messages.get_chat_history(
                contact.id, limit=50, offset=0
            )

            target_clean = target_wamid.replace("wamid.", "")
            try:
                target_suffix = base64.b64decode(target_clean)[-8:]
            except Exception:
                return None

            for m in last_msgs:
                if not m.wamid:
                    continue
                try:
                    m_suffix = base64.b64decode(m.wamid.replace("wamid.", ""))[-8:]
                    if m_suffix == target_suffix:
                        return m
                except Exception:
                    continue
            return None
        except Exception as e:
            logger.error(f"Fuzzy search error: {e}")
            return None
