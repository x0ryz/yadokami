from uuid import UUID

from src.core.exceptions import NotFoundError
from src.core.uow import UnitOfWork
from src.models.base import get_utc_now
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
        uow: UnitOfWork,
        notifier: NotificationService,
        storage: StorageService | None = None,
    ):
        self.uow = uow
        self.notifier = notifier
        self.storage = storage or StorageService()

    async def get_chat_history(
        self, contact_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[MessageResponse]:
        """
        Get chat history with a contact.

        Args:
            contact_id: UUID of the contact
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of messages in chronological order (oldest first)

        Raises:
            NotFoundError: If contact doesn't exist
        """
        async with self.uow:
            # Verify contact exists
            contact = await self.uow.contacts.get_by_id(contact_id)
            if not contact:
                raise NotFoundError(detail="Contact not found")

            # Mark messages as read
            await self._mark_as_read(contact)

            # Get messages
            messages = await self.uow.messages.get_chat_history(
                contact_id, limit, offset
            )

            # Format response
            return await self._format_messages(messages)

    async def _mark_as_read(self, contact):
        """Mark messages as read and notify frontend sidebar."""
        if contact.unread_count > 0:
            contact.unread_count = 0
            self.uow.session.add(contact)
            await self.uow.session.flush()

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

            await self.uow.commit()

    async def _format_messages(self, messages) -> list[MessageResponse]:
        """
        Format messages with presigned media URLs.

        Args:
            messages: List of Message objects with media_files loaded

        Returns:
            List of MessageResponse DTOs in chronological order
        """
        response_data = []

        for msg in messages:
            # Format media files
            media_dtos = await self._format_media_files(msg.media_files)

            # Create message DTO
            msg_dto = MessageResponse(
                id=msg.id,
                wamid=msg.wamid,
                direction=msg.direction,
                status=msg.status,
                message_type=msg.message_type,
                body=msg.body,
                created_at=msg.created_at,
                media_files=media_dtos,
            )

            response_data.append(msg_dto)

        # Return in chronological order (oldest first)
        return list(reversed(response_data))

    async def _format_media_files(self, media_files) -> list[MediaFileResponse]:
        """
        Generate presigned URLs for media files.

        Args:
            media_files: List of MediaFile objects

        Returns:
            List of MediaFileResponse DTOs with presigned URLs
        """
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
        async with self.uow:
            contact = await self.uow.contacts.get_by_id(contact_id)
            if not contact:
                raise NotFoundError(detail="Contact not found")

            await self._mark_as_read(contact)
