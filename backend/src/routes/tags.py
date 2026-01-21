from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_session
from src.core.exceptions import BadRequestError, NotFoundError
from src.repositories.tag import TagRepository
from src.schemas.tags import TagCreate, TagResponse, TagUpdate

router = APIRouter(tags=["Tags"])


@router.get("/tags", response_model=list[TagResponse])
async def get_tags(session: AsyncSession = Depends(get_session)):
    return await TagRepository(session).get_all()


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(data: TagCreate, session: AsyncSession = Depends(get_session)):
    repo = TagRepository(session)
    try:
        tag = await repo.create(data.model_dump())
        await session.commit()
        await session.refresh(tag)
        return tag
    except IntegrityError:
        # Revert session if unique constraint error occurs
        await session.rollback()
        raise BadRequestError(detail="Tag with this name already exists")


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: UUID, session: AsyncSession = Depends(get_session)):
    """Remove a tag"""
    repo = TagRepository(session)
    tag = await repo.get_by_id(tag_id)

    if not tag:
        raise NotFoundError(detail="Tag not found")

    await repo.delete(tag_id)
    await session.commit()


@router.patch("/tags/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: UUID, data: TagUpdate, session: AsyncSession = Depends(get_session)
):
    """Update a tag"""
    repo = TagRepository(session)
    update_data = data.model_dump(exclude_unset=True)

    tag = await repo.update(tag_id, update_data)
    if not tag:
        raise NotFoundError(detail="Tag not found")

    await session.commit()
    await session.refresh(tag)
    return tag
