from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from sqlmodel import desc, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.database import get_session
from src.core.uow import UnitOfWork
from src.models import Contact, Message, get_utc_now
from src.schemas import MediaFileResponse, MessageResponse
from src.services.storage import StorageService

router = APIRouter(tags=["Contacts"])


class ContactUpdate(BaseModel):
    """Schema for updating contact"""

    name: str | None = None
    tags: list[str] | None = None


class ContactCreate(BaseModel):
    """Schema for creating contact"""

    phone_number: str
    name: str | None = None
    tags: list[str] = []


@router.get("/contacts", response_model=list[Contact])
async def get_contacts(session: AsyncSession = Depends(get_session)):
    """Get all contacts sorted by unread count and last activity"""
    statement = select(Contact).order_by(
        desc(Contact.unread_count), desc(Contact.updated_at)
    )
    result = await session.exec(statement)
    contacts = result.all()
    return contacts


@router.get("/contacts/search")
async def search_contacts(
    q: str, limit: int = 50, session: AsyncSession = Depends(get_session)
):
    """
    Search contacts by phone number or name.

    - **q**: Search query (phone or name)
    - **limit**: Maximum results to return
    """
    stmt = (
        select(Contact)
        .where(or_(Contact.phone_number.contains(q), Contact.name.ilike(f"%{q}%")))
        .limit(limit)
    )
    result = await session.exec(stmt)
    contacts = result.all()
    return contacts


@router.post("/contacts", response_model=Contact, status_code=status.HTTP_201_CREATED)
async def create_contact(
    data: ContactCreate, session: AsyncSession = Depends(get_session)
):
    """
    Create a new contact manually.
    """
    uow = UnitOfWork(lambda: session)

    async with uow:
        # Check if contact already exists
        existing = await uow.contacts.get_by_phone(data.phone_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact with this phone number already exists",
            )

        contact = Contact(
            phone_number=data.phone_number,
            name=data.name,
            tags=data.tags,
            source="manual",
            created_at=get_utc_now(),
            updated_at=get_utc_now(),
        )
        uow.session.add(contact)
        await uow.session.flush()
        await uow.session.refresh(contact)

        return contact


@router.get("/contacts/{contact_id}", response_model=Contact)
async def get_contact(contact_id: UUID, session: AsyncSession = Depends(get_session)):
    """Get single contact by ID"""
    contact = await session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return contact


@router.patch("/contacts/{contact_id}", response_model=Contact)
async def update_contact(
    contact_id: UUID, data: ContactUpdate, session: AsyncSession = Depends(get_session)
):
    """
    Update contact details.

    - **name**: Update contact name
    - **tags**: Update contact tags
    """
    contact = await session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(contact, key, value)

    contact.updated_at = get_utc_now()
    session.add(contact)
    await session.commit()
    await session.refresh(contact)

    return contact


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: UUID, session: AsyncSession = Depends(get_session)
):
    """
    Delete a contact.

    This will also delete all associated messages.
    """
    contact = await session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    await session.delete(contact)
    await session.commit()


@router.post("/contacts/{contact_id}/mark-read", response_model=Contact)
async def mark_contact_as_read(
    contact_id: UUID, session: AsyncSession = Depends(get_session)
):
    """
    Mark all messages from this contact as read.
    """
    contact = await session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    contact.unread_count = 0
    contact.updated_at = get_utc_now()
    session.add(contact)
    await session.commit()
    await session.refresh(contact)

    return contact


@router.get("/contacts/{contact_id}/messages", response_model=list[MessageResponse])
async def get_chat_history(
    contact_id: UUID,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """
    Get chat history with a contact.

    Automatically marks messages as read.
    """
    contact = await session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if contact.unread_count > 0:
        contact.unread_count = 0
        session.add(contact)
        await session.commit()

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
