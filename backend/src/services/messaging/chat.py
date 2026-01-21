from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.models.base import get_utc_now
from src.repositories.contact import ContactRepository
from src.repositories.message import MessageRepository
from src.schemas.messages import MediaFileResponse, MessageResponse
from src.services.media.storage import StorageService
from src.services.notifications.service import NotificationService


class ChatService:
    """
    Service for managing chat history.

    Responsibilities:
    - Retrieve message history
    - Mark messages as read
    - Format messages with media URLs
    """

    def __init__(
        self,
        session: AsyncSession,
        notifier: NotificationService,
        storage: StorageService | None = None,
    ):
        self.session = session
        self.notifier = notifier
        self.storage = storage or StorageService()

        # Ініціалізуємо репозиторії
        self.contacts = ContactRepository(session)
        self.messages = MessageRepository(session)

    async def get_chat_history(
        self, contact_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[MessageResponse]:
        """Get chat history with a contact."""

        # Verify contact exists
        contact = await self.contacts.get_by_id(contact_id)
        if not contact:
            raise NotFoundError(detail="Contact not found")

        # Mark messages as read
        await self._mark_as_read(contact)

        # Get messages
        messages = await self.messages.get_chat_history(contact_id, limit, offset)

        # Format response
        return await self._format_messages(messages)

    async def _mark_as_read(self, contact):
        """Mark messages as read and notify frontend sidebar."""
        if contact.unread_count > 0:
            contact.unread_count = 0
            self.session.add(contact)
            await self.session.flush()

            await self.notifier._publish(
                {
                    "event": "contact_updated",
                    "data": {
                        "id": str(contact.id),
                        "phone_number": contact.phone_number,
                        "unread_count": 0,
                        "last_message_at": contact.last_message_at.isoformat()
                        if contact.last_message_at
                        else None,
                    },
                    "timestamp": get_utc_now().isoformat(),
                }
            )

            await self.session.commit()

    async def _format_messages(self, messages) -> list[MessageResponse]:
        """Format messages with presigned media URLs."""
        response_data = []

        for msg in messages:
            media_dtos = await self._format_media_files(msg.media_files)

            msg_dto = MessageResponse(
                id=msg.id,
                wamid=msg.wamid,
                direction=msg.direction,
                status=msg.status,
                message_type=msg.message_type,
                body=msg.body,
                created_at=msg.created_at,
                media_files=media_dtos,
                reply_to_message_id=msg.reply_to_message_id,
                reaction=msg.reaction,
            )

            response_data.append(msg_dto)

        return list(reversed(response_data))

    async def _format_media_files(self, media_files) -> list[MediaFileResponse]:
        """Generate presigned URLs for media files."""
        media_dtos = []

        for mf in media_files:
            url = await self.storage.get_presigned_url(mf.r2_key)

            media_dtos.append(
                MediaFileResponse(
                    id=mf.id,
                    file_name=mf.file_name,
                    file_mime_type=mf.file_mime_type,
                    url=url,
                    caption=mf.caption,
                )
            )

        return media_dtos

    async def mark_conversation_as_read(self, contact_id: UUID):
        """Mark conversation as read without fetching history."""
        contact = await self.contacts.get_by_id(contact_id)
        if not contact:
            raise NotFoundError(detail="Contact not found")

        await self._mark_as_read(contact)
