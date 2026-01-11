from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from src.core.dependencies import get_chat_service, get_uow
from src.core.exceptions import BadRequestError, NotFoundError
from src.core.uow import UnitOfWork
from src.schemas import MessageResponse
from src.schemas.contacts import (
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
)
from src.services.messaging.chat import ChatService

router = APIRouter(tags=["Contacts"])


@router.get("/contacts", response_model=list[ContactListResponse])
async def get_contacts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tags: list[UUID] = Query(default=None),
    uow: UnitOfWork = Depends(get_uow),
):
    """Get all contacts sorted by unread count and last activity"""
    async with uow:
        contacts = await uow.contacts.get_paginated(limit, offset, tag_ids=tags)
        return contacts


@router.get("/contacts/search")
async def search_contacts(q: str, limit: int = 50, uow: UnitOfWork = Depends(get_uow)):
    """Search contacts by phone number or name."""
    async with uow:
        contacts = await uow.contacts.search(q, limit)
        return contacts


@router.post("/contacts", response_model=ContactResponse, status_code=201)
async def create_contact(data: ContactCreate, uow: UnitOfWork = Depends(get_uow)):
    async with uow:
        contact = await uow.contacts.create_manual(data)
        if not contact:
            raise BadRequestError(detail="Contact exists")

        await uow.commit()
        await uow.session.refresh(contact)
        return contact


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    """Get single contact by ID"""
    async with uow:
        contact = await uow.contacts.get_by_id(contact_id)
        if not contact:
            raise NotFoundError(detail="Contact not found")
        return contact


@router.patch("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: UUID, data: ContactUpdate, uow: UnitOfWork = Depends(get_uow)
):
    """Update contact details."""
    async with uow:
        contact = await uow.contacts.update(contact_id, data)
        if not contact:
            raise NotFoundError(detail="Contact not found")

        await uow.commit()
        await uow.session.refresh(contact)

        return contact


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    """Delete a contact."""
    async with uow:
        contact = await uow.contacts.get_by_id(contact_id)
        if not contact:
            raise NotFoundError(detail="Contact not found")

        await uow.contacts.delete(contact_id)
        await uow.commit()


@router.get("/contacts/{contact_id}/messages", response_model=list[MessageResponse])
async def get_chat_history(
    contact_id: UUID,
    limit: int = 50,
    offset: int = 0,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Get chat history with a contact."""
    messages = await chat_service.get_chat_history(contact_id, limit, offset)
    return messages


@router.post("/contacts/{contact_id}/read", status_code=204)
async def mark_contact_read(
    contact_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Mark all messages from a contact as read."""
    await chat_service.mark_conversation_as_read(contact_id)
