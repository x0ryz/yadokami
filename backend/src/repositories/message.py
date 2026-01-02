from sqlalchemy.orm import selectinload
from sqlmodel import select
from src.models import MediaFile, Message, MessageStatus
from src.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self, session):
        super().__init__(session, Message)

    async def create(self, auto_flush: bool = False, **kwargs) -> Message:
        message = Message(**kwargs)
        self.session.add(message)

        if auto_flush:
            await self.session.flush()
            await self.session.refresh(message)

        return message

    async def add_media_file(self, message_id: str, **kwargs) -> MediaFile:
        """Додавання медіа-файлу до повідомлення (замінює MediaRepository)."""
        media_entry = MediaFile(message_id=message_id, **kwargs)
        self.session.add(media_entry)
        return media_entry

    async def get_by_wamid(self, wamid: str) -> Message | None:
        stmt = (
            select(Message)
            .where(Message.wamid == wamid)
            .options(selectinload(Message.contact))
        )
        return (await self.session.exec(stmt)).first()

    async def update_status(self, wamid: str, status: MessageStatus):
        message = await self.get_by_wamid(wamid)
        if message:
            message.status = status
            self.session.add(message)
        return message

    def mark_as_sent(self, message: Message, wamid: str):
        message.wamid = wamid
        message.status = MessageStatus.SENT
        self.session.add(message)

    def mark_as_failed(self, message: Message):
        message.status = MessageStatus.FAILED
        self.session.add(message)
