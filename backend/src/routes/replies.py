from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_session
from src.core.exceptions import BadRequestError, NotFoundError
from src.repositories.reply import QuickReplyRepository
from src.schemas.replies import (
    QuickReplyCreate,
    QuickReplyListResponse,
    QuickReplyResponse,
    QuickReplyTextResponse,
    QuickReplyUpdate,
)

router = APIRouter(prefix="/quick-replies", tags=["Quick Replies"])


@router.get("", response_model=list[QuickReplyResponse])
async def list_quick_replies(
    search: str | None = Query(None, description="Search by title"),
    language: str | None = Query(
        None, description="Filter by available language"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get all quick replies with optional search and language filtering.

    - **search**: Search quick replies by title (case-insensitive)
    - **language**: Filter quick replies that have content in specified language
    """
    repo = QuickReplyRepository(session)
    if search:
        return await repo.search_by_title(search)
    elif language:
        return await repo.get_by_language(language)
    else:
        return await repo.get_all()


@router.post("", response_model=QuickReplyResponse, status_code=status.HTTP_201_CREATED)
async def create_quick_reply(
    data: QuickReplyCreate, session: AsyncSession = Depends(get_session)
):
    """
    Create a new quick reply.

    """
    repo = QuickReplyRepository(session)
    quick_reply = await repo.create(data.model_dump())
    await session.commit()
    await session.refresh(quick_reply)
    return quick_reply


@router.get("/{reply_id}", response_model=QuickReplyResponse)
async def get_quick_reply(reply_id: UUID, session: AsyncSession = Depends(get_session)):
    """
    Get specific quick reply by ID.
    """
    repo = QuickReplyRepository(session)
    quick_reply = await repo.get_by_id(reply_id)
    if not quick_reply:
        raise NotFoundError(detail="Quick reply not found")
    return quick_reply


@router.patch("/{reply_id}", response_model=QuickReplyResponse)
async def update_quick_reply(
    reply_id: UUID, data: QuickReplyUpdate, session: AsyncSession = Depends(get_session)
):
    """
    Update a quick reply.

    Only provided fields will be updated. All fields are optional.
    """
    repo = QuickReplyRepository(session)
    update_data = data.model_dump(exclude_unset=True)

    quick_reply = await repo.update(reply_id, update_data)
    if not quick_reply:
        raise NotFoundError(detail="Quick reply not found")

    await session.commit()
    await session.refresh(quick_reply)
    return quick_reply


@router.delete("/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quick_reply(reply_id: UUID, session: AsyncSession = Depends(get_session)):
    """
    Delete a quick reply.
    """
    repo = QuickReplyRepository(session)
    success = await repo.delete(reply_id)
    if not success:
        raise NotFoundError(detail="Quick reply not found")
    await session.commit()


@router.get("/{reply_id}/text", response_model=QuickReplyTextResponse)
async def get_quick_reply_text(
    reply_id: UUID,
    language: str = Query(default="uk", description="Language code"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get text content for a quick reply in specified language.

    If the requested language is not available, returns content in the default language.
    """
    repo = QuickReplyRepository(session)
    quick_reply = await repo.get_by_id(reply_id)
    if not quick_reply:
        raise NotFoundError(detail="Quick reply not found")

    text = quick_reply.get_text(language)
    
    actual_language = language
    if language not in quick_reply.content and quick_reply.content:
        # Fallback to the first available language key
        actual_language = next(iter(quick_reply.content.keys()))

    return QuickReplyTextResponse(text=text, language=actual_language)


@router.post("/{reply_id}/languages/{language}", response_model=QuickReplyResponse)
async def add_language_content(
    reply_id: UUID,
    language: str,
    content: str = Query(..., description="Text content for the language"),
    session: AsyncSession = Depends(get_session),
):
    """
    Add or update content for a specific language in a quick reply.
    """
    repo = QuickReplyRepository(session)
    quick_reply = await repo.get_by_id(reply_id)
    if not quick_reply:
        raise NotFoundError(detail="Quick reply not found")

    # Update content with new language
    new_content = quick_reply.content.copy()
    new_content[language] = content

    updated_reply = await repo.update(
        reply_id, {"content": new_content}
    )
    await session.commit()
    await session.refresh(updated_reply)
    return updated_reply


@router.delete("/{reply_id}/languages/{language}", response_model=QuickReplyResponse)
async def remove_language_content(
    reply_id: UUID, language: str, session: AsyncSession = Depends(get_session)
):
    """
    Remove content for a specific language from a quick reply.

    Cannot remove the default language content.
    """
    repo = QuickReplyRepository(session)
    quick_reply = await repo.get_by_id(reply_id)
    if not quick_reply:
        raise NotFoundError(detail="Quick reply not found")

    if len(quick_reply.content) <= 1:
        raise BadRequestError(detail="Cannot remove the last remaining language content")

    if language not in quick_reply.content:
        raise BadRequestError(
            detail=f"Language '{language}' not found in quick reply content"
        )

    # Update content by removing the language
    new_content = quick_reply.content.copy()
    del new_content[language]

    updated_reply = await repo.update(
        reply_id, {"content": new_content}
    )
    await session.commit()
    await session.refresh(updated_reply)
    return updated_reply


@router.get("/stats/summary")
async def get_quick_reply_stats(session: AsyncSession = Depends(get_session)):
    """
    Get statistics about quick replies.

    Returns total count, unique languages, and available languages list.
    """
    repo = QuickReplyRepository(session)
    total_count = await repo.count_all()
    all_replies = await repo.get_all()

    # Count unique languages
    languages = set()
    for reply in all_replies:
        languages.update(reply.content.keys())

    return {
        "total_quick_replies": total_count,
        "unique_languages": len(languages),
        "available_languages": sorted(list(languages)),
    }
