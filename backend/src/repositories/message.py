import base64
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, exists, func, select
from sqlalchemy.orm import selectinload

from src.models import MediaFile, Message, MessageDirection, MessageStatus
from src.repositories.base import BaseRepository
from src.schemas import MetaMessage


class MessageRepository(BaseRepository[Message]):
    def __init__(self, session):
        super().__init__(session, Message)

    async def create(self, **kwargs) -> Message:
        message = Message(**kwargs)
        self.session.add(message)
        return message

    async def add_media_file(self, message_id: UUID | str, **kwargs) -> MediaFile:
        media_entry = MediaFile(message_id=message_id, **kwargs)
        self.session.add(media_entry)
        return media_entry

    async def get_by_wamid(self, wamid: str) -> Message | None:
        stmt = (
            select(Message)
            .where(Message.wamid == wamid)
            .options(selectinload(Message.contact))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def exists_by_wamid(self, wamid: str) -> bool:
        """Quick check for existence of message (for deduplication)."""
        stmt = select(exists().where(Message.wamid == wamid))
        return await self.session.scalar(stmt)

    async def resolve_reply_id(self, msg: MetaMessage, contact_id: UUID) -> UUID | None:
        """
        Finds ID of parent message.
        First tries exact match, then fuzzy search.
        """
        if not msg.context or not msg.context.id:
            return None

        ctx_wamid = msg.context.id

        # Try exact match
        stmt = select(Message.id).where(Message.wamid == ctx_wamid)
        parent_id = await self.session.scalar(stmt)

        if parent_id:
            return parent_id

        # If not found, try fuzzy search
        parent_msg = await self._fuzzy_find_message(contact_id, ctx_wamid)
        return parent_msg.id if parent_msg else None

    async def get_by_id(self, id: UUID) -> Message | None:
        stmt = (
            select(Message)
            .where(Message.id == id)
            .options(
                selectinload(Message.media_files),
                selectinload(Message.contact),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, wamid: str, status: MessageStatus) -> Message | None:
        message = await self.get_by_wamid(wamid)
        if message:
            message.status = status
            self.session.add(message)
        return message

    async def get_chat_history(
        self, contact_id: UUID, limit: int, offset: int
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.contact_id == contact_id)
            .options(
                selectinload(Message.media_files),
                selectinload(Message.parent_message).options(
                    selectinload(Message.media_files)
                ),
            )
            .order_by(desc(Message.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # --- Statistics Methods ---

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(Message)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_by_direction(self, direction: MessageDirection) -> int:
        stmt = select(func.count()).where(Message.direction == direction)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_recent(self, since: datetime) -> int:
        stmt = select(func.count()).where(Message.created_at >= since)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_delivered_outbound(self) -> int:
        stmt = select(func.count()).where(
            Message.direction == MessageDirection.OUTBOUND,
            Message.status == MessageStatus.DELIVERED,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_recent(self, limit: int) -> list[Message]:
        stmt = select(Message).order_by(desc(Message.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_after(self, timestamp: datetime) -> list[Message]:
        stmt = select(Message).where(Message.created_at >= timestamp)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_campaign_message_for_contact(
        self, contact_id: UUID
    ) -> Message | None:
        stmt = (
            select(Message)
            .where(
                Message.contact_id == contact_id,
                Message.direction == MessageDirection.OUTBOUND,
                Message.status.in_(
                    [MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ]
                ),
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def _fuzzy_find_message(
        self, contact_id: UUID, target_wamid: str
    ) -> Message | None:
        """
        Internal helper: Attempts to find a message by fuzzy matching WAMID suffixes.
        Uses existing session and contact_id (more efficient than phone lookup).
        """
        try:
            last_msgs = await self.get_chat_history(contact_id, limit=50, offset=0)

            target_clean = target_wamid.replace("wamid.", "")

            try:
                target_suffix = base64.b64decode(target_clean)[-8:]
            except Exception:
                return None

            for m in last_msgs:
                if not m.wamid:
                    continue
                try:
                    m_clean = m.wamid.replace("wamid.", "")
                    m_suffix = base64.b64decode(m_clean)[-8:]

                    if m_suffix == target_suffix:
                        return m
                except Exception:
                    continue

            return None
        except Exception:
            return None

    async def has_received_template(
        self, contact_id: UUID, template_id: UUID
    ) -> bool:
        """Check if contact has already received a message with this template."""
        stmt = select(exists().where(
            Message.contact_id == contact_id,
            Message.template_id == template_id,
            Message.direction == MessageDirection.OUTBOUND
        ))
        return await self.session.scalar(stmt)
