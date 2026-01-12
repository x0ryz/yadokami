from uuid import UUID
import io
import pandas as pd

from fastapi import APIRouter, Depends, Query, status, UploadFile, File
from src.core.dependencies import get_chat_service, get_uow
from src.core.exceptions import BadRequestError, NotFoundError
from src.core.uow import UnitOfWork
from src.models.base import ContactStatus
from src.schemas import MessageResponse
from src.schemas.contacts import (
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
    ContactImportResult,
)
from src.services.messaging.chat import ChatService

router = APIRouter(tags=["Contacts"])


@router.get("/contacts", response_model=list[ContactListResponse])
async def get_contacts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tags: list[UUID] = Query(default=None),
    status: ContactStatus | None = Query(default=None),
    uow: UnitOfWork = Depends(get_uow),
):
    """Get all contacts sorted by unread count and last activity"""
    async with uow:
        contacts = await uow.contacts.get_paginated(
            limit, offset, tag_ids=tags, status=status
        )
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


@router.post("/contacts/import", response_model=ContactImportResult)
async def import_contacts(
    file: UploadFile = File(...),
    uow: UnitOfWork = Depends(get_uow)
):
    """Import contacts from Excel or CSV file."""
    if not file.filename:
        raise BadRequestError("File must have a name")

    content = await file.read()

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise BadRequestError("Unsupported file format. Use CSV or Excel.")
    except Exception as e:
        raise BadRequestError(f"Error reading file: {str(e)}")

    # Normalize columns to lower case
    df.columns = df.columns.astype(str).str.lower()

    imported_count = 0
    skipped_count = 0
    errors = []

    async with uow:
        for index, row in df.iterrows():
            try:
                # Basic extraction logic - try to find columns
                phone = None
                name = None
                link = None

                # Naive column matching
                for col in df.columns:
                    val = str(row[col]) if not pd.isna(row[col]) else None
                    if not val:
                        continue

                    if 'phone' in col or 'телефон' in col:
                        phone = val
                    elif 'name' in col or 'ім\'я' in col or 'имя' in col:
                        name = val
                    elif 'link' in col or 'url' in col or 'силка' in col:
                        link = val

                if not phone:
                    # Try to treat the first column as phone if explicitly not found?
                    # Or just skip. User said "I have such file", assuming headers exist.
                    # If simplified, maybe user wants us to guess column by content?
                    # Sticking to column names for now as it's safer.
                    continue

                # Clean phone number
                phone_digits = "".join(c for c in phone if c.isdigit())

                if len(phone_digits) < 10:
                    errors.append(
                        f"Row {index + 1}: Invalid phone number '{phone}'")
                    continue

                # Check duplicate
                existing = await uow.contacts.get_by_phone(phone_digits)
                if existing:
                    skipped_count += 1
                    continue

                # Create contact
                contact_data = ContactCreate(
                    phone_number=phone_digits,
                    name=name,
                    link=link,
                    tag_ids=[]
                )

                await uow.contacts.create_manual(contact_data)
                imported_count += 1

            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")

        await uow.commit()

    return ContactImportResult(
        total=len(df),
        imported=imported_count,
        skipped=skipped_count,
        errors=errors
    )


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
