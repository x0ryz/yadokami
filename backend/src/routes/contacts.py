import io
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_chat_service, get_session
from src.core.exceptions import BadRequestError, NotFoundError
from src.models import Contact
from src.models.base import ContactStatus
from src.repositories.contact import ContactRepository
from src.schemas import MessageResponse
from src.schemas.contacts import (
    ContactCreate,
    ContactImportResult,
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
    tags: list[UUID] | None = Query(default=None),
    status: ContactStatus | None = Query(default=None),
    all: bool = Query(
        default=False,
        description="Показати всі контакти (включно з тими, у кого немає тегів)",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Get all contacts sorted by unread count and last activity

    За замовчуванням показує всіх контактів з будь-якими тегами.
    Для перегляду абсолютно всіх контактів (включно з тими, у кого немає тегів) встановіть all=true
    """
    show_only_with_tags = not all

    contacts = await ContactRepository(session).get_paginated(
        limit,
        offset,
        tag_ids=tags,
        status=status,
        show_only_with_tags=show_only_with_tags,
    )
    return contacts


@router.get("/contacts/search")
async def search_contacts(
    q: str, limit: int = 50, session: AsyncSession = Depends(get_session)
):
    """Search contacts by phone number or name."""
    contacts = await ContactRepository(session).search(q, limit)
    return contacts


@router.post("/contacts", response_model=ContactResponse, status_code=201)
async def create_contact(
    data: ContactCreate, session: AsyncSession = Depends(get_session)
):
    repo = ContactRepository(session)
    contact = await repo.create_manual(data)

    if not contact:
        raise BadRequestError(detail="Contact exists")

    await session.commit()
    await session.refresh(contact)
    return contact


@router.post("/contacts/import", response_model=ContactImportResult)
async def import_contacts(
    file: UploadFile = File(...), session: AsyncSession = Depends(get_session)
):
    """Import contacts from Excel or CSV file."""
    if not file.filename:
        raise BadRequestError("File must have a name")

    content = await file.read()

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith((".xls", ".xlsx")):
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

    repo = ContactRepository(session)

    # Використовуємо сесію без "async with uow"
    for idx, (index, row) in enumerate(df.iterrows()):
        try:
            # Basic extraction logic - try to find columns
            phone = None
            name = None
            custom_data = {}

            # Naive column matching
            for col in df.columns:
                val = str(row[col]) if not pd.isna(row[col]) else None
                if not val:
                    continue

                col_lower = col.lower()
                if "phone" in col_lower or "телефон" in col_lower:
                    phone = val
                elif "name" in col_lower or "ім'я" in col_lower or "имя" in col_lower:
                    name = val
                elif "link" in col_lower or "url" in col_lower or "силка" in col_lower:
                    custom_data["link"] = val
                else:
                    # Додаємо всі інші колонки в custom_data
                    custom_data[col] = val

            if not phone:
                continue

            # Clean phone number
            phone_digits = "".join(c for c in phone if c.isdigit())

            if len(phone_digits) < 10:
                errors.append(f"Row {idx + 2}: Invalid phone number '{phone}'")
                continue

            # Check duplicate
            existing = await repo.get_by_phone(phone_digits)
            if existing:
                skipped_count += 1
                continue

            # Create contact
            contact_data = ContactCreate(
                phone_number=phone_digits,
                name=name,
                custom_data=custom_data,
                tag_ids=[],
            )

            await repo.create_manual(contact_data)
            imported_count += 1

        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")

    await session.commit()

    return ContactImportResult(
        total=len(df), imported=imported_count, skipped=skipped_count, errors=errors
    )


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: UUID, session: AsyncSession = Depends(get_session)):
    """Get single contact by ID"""
    contact = await ContactRepository(session).get_by_id(contact_id)
    if not contact:
        raise NotFoundError(detail="Contact not found")
    return contact


@router.patch("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: UUID, data: ContactUpdate, session: AsyncSession = Depends(get_session)
):
    """Update contact details."""
    repo = ContactRepository(session)
    contact = await repo.update(contact_id, data)

    if not contact:
        raise NotFoundError(detail="Contact not found")

    await session.commit()
    await session.refresh(contact)

    return contact


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Delete a contact."""
    repo = ContactRepository(session)
    contact = await repo.get_by_id(contact_id)

    if not contact:
        raise NotFoundError(detail="Contact not found")

    await repo.delete(contact_id)
    await session.commit()


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


@router.get("/contacts/fields/available")
async def get_available_fields(
    session: AsyncSession = Depends(get_session),
):
    """
    Get all available fields from all contacts in the system.
    Returns standard fields and all unique custom_data keys.
    """
    # Query all contacts directly without status filtering
    query = select(Contact)
    result = await session.execute(query)
    contacts = result.scalars().all()

    # Standard fields that are always available
    standard_fields = ["name", "phone_number"]

    # Collect all unique custom_data keys
    custom_fields_set = set()
    for contact in contacts:
        if contact.custom_data:
            custom_fields_set.update(contact.custom_data.keys())

    custom_fields = sorted(list(custom_fields_set))

    return {
        "standard_fields": standard_fields,
        "custom_fields": custom_fields,
        "total_contacts": len(contacts),
    }
