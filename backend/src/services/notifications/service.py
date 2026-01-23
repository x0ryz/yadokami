from uuid import UUID

from loguru import logger

from src.core.broker import broker
from src.models import Message, get_utc_now
from src.schemas.events import (
    BatchProgressEvent,
    CampaignProgressEvent,
    CampaignStatusEvent,
    ContactSessionUpdateEvent,
    IncomingMessageEvent,
    MessageStatusEvent,
)


class NotificationService:
    async def _publish(self, event_data: dict):
        """Low-level publish to NATS"""
        try:
            await broker.publish(
                event_data,
                subject="ws_updates",
            )
        except Exception as e:
            logger.error(f"Failed to publish WS update: {e}")

    async def notify_new_message(
        self, message: Message, media_files: list[dict] = None, phone: str = None
    ):
        contact_phone = phone
        if not contact_phone and message.contact:
            contact_phone = message.contact.phone_number

        event = IncomingMessageEvent(
            message_id=message.id,
            contact_id=message.contact_id,
            phone=contact_phone,
            type=message.message_type,
            body=message.body,
            wamid=message.wamid,
            media_files=media_files or [],
            created_at=message.created_at,
            direction=message.direction,
            status=message.status,
            reply_to_message_id=message.reply_to_message_id,
            reaction=message.reaction,
        )
        await self._publish(event.to_dict())

    async def notify_message_reaction(
        self, message_id: UUID, reaction: str | None, phone: str
    ):
        event = {
            "event": "message_reaction",
            "data": {
                "message_id": str(message_id),
                "reaction": reaction,
                "phone": phone,
            },
            "timestamp": get_utc_now().isoformat(),
        }
        await self._publish(event)

    async def notify_contact_session_update(
        self,
        contact_id: UUID,
        phone: str,
        last_message_at,
        last_incoming_message_at=None,
    ):
        """Notify about contact session time update (for 24h window tracking)"""
        event = ContactSessionUpdateEvent(
            contact_id=contact_id,
            phone=phone,
            last_message_at=last_message_at,
            last_incoming_message_at=last_incoming_message_at,
        )
        await self._publish(event.to_dict())

    async def notify_message_status(
        self, message_id: UUID, wamid: str, status: str, **kwargs
    ):
        event = MessageStatusEvent(
            message_id=message_id, wamid=wamid, status=status, **kwargs
        )
        await self._publish(event.to_dict())

    async def notify_campaign_progress(self, campaign_id: UUID, stats: dict):
        event = CampaignProgressEvent(campaign_id=campaign_id, **stats)
        await self._publish(event.to_dict())

    async def notify_campaign_status(self, campaign_id: UUID, status: str, **kwargs):
        event = CampaignStatusEvent(
            campaign_id=campaign_id, status=status, **kwargs)
        await self._publish(event.to_dict())

    async def notify_batch_progress(
        self, campaign_id: UUID, batch_number: int, stats: dict
    ):
        event = BatchProgressEvent(
            campaign_id=campaign_id, batch_number=batch_number, **stats
        )
        await self._publish(event.to_dict())

    async def notify_template_update(
        self, template_id: str, name: str, status: str, reason: str | None = None
    ):
        event = {
            "event": "template_status_update",
            "data": {
                "id": template_id,
                "name": name,
                "status": status,
                "reason": reason,
            },
            "timestamp": get_utc_now().isoformat(),
        }
        await self._publish(event)

    async def notify_waba_update(self, waba_id: str, status: str, event_type: str):
        event = {
            "event": "waba_status_update",
            "data": {
                "waba_id": waba_id,
                "status": status,
                "type": event_type,
            },
            "timestamp": get_utc_now().isoformat(),
        }
        await self._publish(event)

    async def notify_phone_update(
        self, phone_number: str, event: str, current_limit: str
    ):
        event = {
            "event": "phone_status_update",
            "data": {
                "display_phone_number": phone_number,
                "event": event,
                "messaging_limit_tier": current_limit,
            },
            "timestamp": get_utc_now().isoformat(),
        }
        await self._publish(event)
