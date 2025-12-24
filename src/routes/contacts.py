from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.database import get_session
from src.models import Contact, Message
from src.schemas import MediaFileResponse, MessageResponse
from src.services.storage import StorageService

router = APIRouter(tags=["Contacts"])


@router.get("/contacts", response_model=list[Contact])
async def get_contacts(session: AsyncSession = Depends(get_session)):
    statement = select(Contact).order_by(desc(Contact.updated_at))
    result = await session.exec(statement)
    contacts = result.all()
    return contacts


@router.get("/contacts/{contact_id}/messages", response_model=list[MessageResponse])
async def get_chat_history(
    contact_id: UUID,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    contact = await session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    statement = (
        select(Message)
        .where(Message.contact_id == contact_id)
        .options(selectinload(Message.media_files))
        .order_by(desc(Message.created_at))
        .offset(offset)
        .limit(limit)
    )

    result = await session.exec(statement)
    messages = result.all()

    storage = StorageService()
    response_data = []

    for msg in messages:
        media_dtos = []
        for mf in msg.media_files:
            url = await storage.get_presigned_url(mf.r2_key)
            media_dtos.append(
                MediaFileResponse(
                    id=mf.id,
                    file_name=mf.file_name,
                    file_mime_type=mf.file_mime_type,
                    url=url,
                    caption=mf.caption,
                )
            )

        response_data.append(
            MessageResponse(
                id=msg.id,
                wamid=msg.wamid,
                direction=msg.direction,
                status=msg.status,
                message_type=msg.message_type,
                body=msg.body,
                created_at=msg.created_at,
                media_files=media_dtos,
            )
        )

    return list(reversed(response_data))
