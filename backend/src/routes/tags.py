from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from src.core.dependencies import get_uow
from src.core.exceptions import BadRequestError, NotFoundError
from src.core.uow import UnitOfWork
from src.schemas.tags import TagCreate, TagResponse

router = APIRouter(tags=["Tags"])


@router.get("/tags", response_model=list[TagResponse])
async def get_tags(uow: UnitOfWork = Depends(get_uow)):
    async with uow:
        return await uow.tags.get_all()


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(data: TagCreate, uow: UnitOfWork = Depends(get_uow)):
    async with uow:
        try:
            tag = await uow.tags.create(data.model_dump())
            await uow.commit()
            await uow.session.refresh(tag)
            return tag
        except IntegrityError:
            raise BadRequestError(detail="Tag with this name already exists")


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    """Видалити тег (автоматично зникне у всіх контактів)."""
    async with uow:
        tag = await uow.tags.get_by_id(tag_id)
        if not tag:
            raise NotFoundError(detail="Tag not found")

        await uow.tags.delete(tag_id)
        await uow.commit()
