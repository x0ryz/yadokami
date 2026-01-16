import base64

from loguru import logger
from src.core.uow import UnitOfWork
from src.models import (
    CampaignDeliveryStatus,
    MessageDirection,
    MessageStatus,
    get_utc_now,
)
from src.schemas import (
    MetaAccountReviewUpdate,
    MetaMessage,
    MetaPhoneNumberQualityUpdate,
    MetaStatus,
    MetaTemplateUpdate,
    MetaWebhookPayload,
)
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
        for entry in webhook.entry:
            waba_id = entry.id

            for change in entry.changes:
                value = change.value

                if value.message_template_status_update:
                    await self._handle_template_update(
                        value.message_template_status_update
                    )

                elif value.account_review_update:
                    await self._handle_account_review(
                        waba_id, value.account_review_update
                    )

                elif value.phone_number_quality_update:
                    await self._handle_phone_quality(value.phone_number_quality_update)

                if value.messages:
                    phone_id = value.metadata.get("phone_number_id")
                    if phone_id:
                        await self._handle_messages(value.messages, phone_id)

                if value.statuses:
                    await self._handle_statuses(value.statuses)

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
                    self.uow.messages.add(db_message)

                    campaign_link = await self.uow.campaign_contacts.get_by_message_id(
                        db_message.id
                    )

                    if campaign_link:
                        if campaign_link.status == CampaignDeliveryStatus.REPLIED:
                            continue

                        if new_status == MessageStatus.DELIVERED:
                            if campaign_link.status not in [
                                CampaignDeliveryStatus.READ,
                                CampaignDeliveryStatus.FAILED,
                            ]:
                                campaign_link.status = CampaignDeliveryStatus.DELIVERED

                            campaign = await self.uow.campaigns.get_by_id(
                                campaign_link.campaign_id
                            )
                            if campaign:
                                campaign.delivered_count += 1
                                campaign.sent_count -= 1
                                self.uow.campaigns.add(campaign)

                        elif new_status == MessageStatus.READ:
                            campaign_link.status = CampaignDeliveryStatus.READ
                            campaign = await self.uow.campaigns.get_by_id(
                                campaign_link.campaign_id
                            )
                            if campaign:
                                campaign.read_count += 1
                                campaign.delivered_count -= 1
                                self.uow.campaigns.add(campaign)

                        elif new_status == MessageStatus.FAILED:
                            campaign_link.status = CampaignDeliveryStatus.FAILED
                            campaign = await self.uow.campaigns.get_by_id(
                                campaign_link.campaign_id
                            )
                            if campaign:
                                campaign.failed_count += 1
                                self.uow.campaigns.add(campaign)

                        self.uow.campaign_contacts.add(campaign_link)

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
                        self.uow.messages.add(target_msg)
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
                    body = f"Location: {loc.name or ''} {loc.address or ''} ({loc.latitude}, {loc.longitude})".strip(
                    )
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

                latest_campaign_message = (
                    await self.uow.messages.get_latest_campaign_message_for_contact(
                        contact.id
                    )
                )

                if latest_campaign_message:
                    campaign_link = await self.uow.campaign_contacts.get_by_message_id(
                        latest_campaign_message.id
                    )

                    if (
                        campaign_link
                        and campaign_link.status != CampaignDeliveryStatus.REPLIED
                    ):
                        campaign = await self.uow.campaigns.get_by_id(
                            campaign_link.campaign_id
                        )

                        if campaign:
                            campaign.replied_count += 1

                            if campaign_link.status == CampaignDeliveryStatus.READ:
                                campaign.read_count = max(
                                    0, campaign.read_count - 1)
                            elif (
                                campaign_link.status == CampaignDeliveryStatus.DELIVERED
                            ):
                                campaign.delivered_count = max(
                                    0, campaign.delivered_count - 1
                                )
                            elif campaign_link.status == CampaignDeliveryStatus.SENT:
                                campaign.sent_count = max(
                                    0, campaign.sent_count - 1)

                            self.uow.campaigns.add(campaign)

                            campaign_link.status = CampaignDeliveryStatus.REPLIED
                            self.uow.campaign_contacts.add(campaign_link)

                            logger.info(
                                f"Campaign {campaign.id}: Contact {contact.phone_number} moved from {campaign_link.status} to REPLIED"
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
                contact.last_message_at = get_utc_now()
                contact.last_incoming_message_at = get_utc_now()
                self.uow.contacts.add(contact)

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
                        logger.info(
                            f"Queued media download for msg {new_msg.id}")

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
        try:
            contact = await self.uow.contacts.get_or_create(phone_number)
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
                    m_suffix = base64.b64decode(
                        m.wamid.replace("wamid.", ""))[-8:]
                    if m_suffix == target_suffix:
                        return m
                except Exception:
                    continue
            return None
        except Exception as e:
            logger.error(f"Fuzzy search error: {e}")
            return None

    async def _handle_template_update(self, update: MetaTemplateUpdate):
        await self.notifier.notify_template_update(
            template_id=update.message_template_id,
            name=update.message_template_name,
            status=update.event,
            reason=update.reason,
        )

        async with self.uow:
            template = await self.uow.templates.get_by_meta_id(
                update.message_template_id
            )
            if template:
                template.status = update.event
                template.updated_at = get_utc_now()
                self.uow.templates.add(template)
                await self.uow.commit()

    async def _handle_account_review(
        self, waba_id: str, update: MetaAccountReviewUpdate
    ):
        await self.notifier.notify_waba_update(
            waba_id=waba_id, status=update.decision, event_type="REVIEW_UPDATE"
        )

        async with self.uow:
            account = await self.uow.waba.get_by_waba_id(waba_id)
            if account:
                account.account_review_status = update.decision
                self.uow.waba.add(account)
                await self.uow.commit()

    async def _handle_phone_quality(self, update: MetaPhoneNumberQualityUpdate):
        await self.notifier.notify_phone_update(
            phone_number=update.display_phone_number,
            event=update.event,
            current_limit=update.current_limit,
        )

        async with self.uow:
            phone = await self.uow.waba.get_by_display_phone(
                update.display_phone_number
            )
            if phone:
                phone.messaging_limit_tier = update.current_limit
                if update.event == "FLAGGED":
                    phone.quality_rating = "RED"
                elif update.event == "UNFLAGGED":
                    phone.quality_rating = "GREEN"
                self.uow.waba.add(phone)
                await self.uow.commit()
