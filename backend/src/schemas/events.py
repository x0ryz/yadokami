from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """All possible WebSocket event types"""

    # Campaign events
    CAMPAIGN_CREATED = "campaign_created"
    CAMPAIGN_UPDATED = "campaign_updated"
    CAMPAIGN_DELETED = "campaign_deleted"
    CAMPAIGN_SCHEDULED = "campaign_scheduled"
    CAMPAIGN_STARTED = "campaign_started"
    CAMPAIGN_PAUSED = "campaign_paused"
    CAMPAIGN_RESUMED = "campaign_resumed"
    CAMPAIGN_COMPLETED = "campaign_completed"
    CAMPAIGN_FAILED = "campaign_failed"
    CAMPAIGN_PROGRESS = "campaign_progress"

    # Message events
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_READ = "message_read"
    MESSAGE_FAILED = "message_failed"
    MESSAGE_RECEIVED = "new_message"

    # Contact events
    CONTACT_CREATED = "contact_created"
    CONTACT_UPDATED = "contact_updated"
    CONTACT_DELETED = "contact_deleted"
    CONTACT_UNREAD_CHANGED = "contact_unread_changed"
    CONTACT_SESSION_UPDATE = "contact_session_update"

    # System events
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"

    # Status updates
    STATUS_UPDATE = "status_update"

    # Batch processing
    BATCH_STARTED = "batch_started"
    BATCH_COMPLETED = "batch_completed"
    BATCH_PROGRESS = "batch_progress"


class WSEvent(BaseModel):
    """Base WebSocket event structure"""

    event: EventType
    data: dict[str, Any]
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)

    def to_dict(self) -> dict:
        return {
            "event": self.event.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class CampaignProgressEvent(WSEvent):
    """Campaign progress update with detailed stats"""

    def __init__(self, campaign_id: UUID, **stats):
        super().__init__(
            event=EventType.CAMPAIGN_PROGRESS,
            data={
                "campaign_id": str(campaign_id),
                "total": stats.get("total", 0),
                "sent": stats.get("sent", 0),
                "delivered": stats.get("delivered", 0),
                "read": stats.get("read", 0),
                "failed": stats.get("failed", 0),
                "pending": stats.get("pending", 0),
                "progress_percent": stats.get("progress_percent", 0),
                "estimated_completion": stats.get("estimated_completion"),
                "current_rate": stats.get("current_rate", 0),
            },
        )


class CampaignStatusEvent(WSEvent):
    """Campaign status change"""

    def __init__(self, campaign_id: UUID, status: str, **extra):
        event_map = {
            "SCHEDULED": EventType.CAMPAIGN_SCHEDULED,
            "RUNNING": EventType.CAMPAIGN_STARTED,
            "PAUSED": EventType.CAMPAIGN_PAUSED,
            "COMPLETED": EventType.CAMPAIGN_COMPLETED,
            "FAILED": EventType.CAMPAIGN_FAILED,
        }

        super().__init__(
            event=event_map.get(status, EventType.CAMPAIGN_UPDATED),
            data={"campaign_id": str(campaign_id), "status": status, **extra},
        )


class BatchProgressEvent(WSEvent):
    """Batch processing progress"""

    def __init__(self, campaign_id: UUID, batch_number: int, **stats):
        super().__init__(
            event=EventType.BATCH_PROGRESS,
            data={
                "campaign_id": str(campaign_id),
                "batch_number": batch_number,
                "batch_size": stats.get("batch_size", 0),
                "processed": stats.get("processed", 0),
                "successful": stats.get("successful", 0),
                "failed": stats.get("failed", 0),
            },
        )


class MessageStatusEvent(WSEvent):
    """Message status update"""

    def __init__(self, message_id: UUID, wamid: str, status: str, **extra):
        event_map = {
            "sent": EventType.MESSAGE_SENT,
            "delivered": EventType.MESSAGE_DELIVERED,
            "read": EventType.MESSAGE_READ,
            "failed": EventType.MESSAGE_FAILED,
        }

        event_type = event_map.get(status, EventType.STATUS_UPDATE)

        super().__init__(
            event=event_type,
            data={
                "message_id": str(message_id),
                "wamid": wamid,
                "status": status,
                "new_status": status,
                **extra,
            },
        )


class IncomingMessageEvent(WSEvent):
    """New incoming message from contact"""

    def __init__(
        self,
        message_id: UUID,
        contact_id: UUID,
        phone: str | None = None,
        reply_to_message_id: UUID | None = None,
        reaction: str | None = None,
        **message_data,
    ):
        data = {
            "id": str(message_id),
            "message_id": str(message_id),
            "contact_id": str(contact_id),
            "phone": phone,
            "phone_number": phone,
            "reply_to_message_id": str(reply_to_message_id)
            if reply_to_message_id
            else None,
            "reaction": reaction,
        }
        data.update(message_data)

        super().__init__(
            event=EventType.MESSAGE_RECEIVED,
            data=data,
        )


class MessageReactionEvent(WSEvent):
    """Message reaction update event"""

    def __init__(
        self,
        message_id: UUID,
        reaction: str | None,
        phone: str | None = None,
    ):
        super().__init__(
            event=EventType.MESSAGE_REACTION,
            data={
                "message_id": str(message_id),
                "reaction": reaction,
                "phone": phone,
            },
        )


class ContactUnreadEvent(WSEvent):
    """Contact unread count changed"""

    def __init__(self, contact_id: UUID, phone: str, unread_count: int):
        super().__init__(
            event=EventType.CONTACT_UNREAD_CHANGED,
            data={
                "contact_id": str(contact_id),
                "phone": phone,
                "unread_count": unread_count,
            },
        )


class ContactSessionUpdateEvent(WSEvent):
    """Contact session time update (last_message_at)"""

    def __init__(
        self,
        contact_id: UUID,
        phone: str,
        last_message_at: datetime,
        last_incoming_message_at: datetime | None = None,
    ):
        super().__init__(
            event=EventType.CONTACT_SESSION_UPDATE,
            data={
                "contact_id": str(contact_id),
                "phone": phone,
                "last_message_at": last_message_at.isoformat(),
                "last_incoming_message_at": last_incoming_message_at.isoformat()
                if last_incoming_message_at
                else None,
            },
        )


class SyncStatusEvent(WSEvent):
    """WABA sync status update"""

    def __init__(self, status: str, **details):
        event_map = {
            "started": EventType.SYNC_STARTED,
            "completed": EventType.SYNC_COMPLETED,
            "failed": EventType.SYNC_FAILED,
        }

        super().__init__(
            event=event_map.get(status, EventType.SYNC_STARTED),
            data={"status": status, **details},
        )


def create_legacy_event(event_type: str, data: dict) -> dict:
    """Convert old-style events to new format"""
    return {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
