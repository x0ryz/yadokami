from uuid import UUID

from fastapi import APIRouter, Depends
from src.core.dependencies import get_uow
from src.core.exceptions import NotFoundError
from src.core.uow import UnitOfWork
from src.schemas import TemplateListResponse, TemplateResponse

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=list[TemplateListResponse])
async def list_templates(uow: UnitOfWork = Depends(get_uow)):
    """
    Get all message templates.

    Returns templates synced from Meta WhatsApp Business API.
    """
    async with uow:
        return await uow.templates.get_all_sorted()


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: UUID, uow: UnitOfWork = Depends(get_uow)):
    """
    Get specific template by ID.
    """
    async with uow:
        template = await uow.templates.get_by_id(template_id)

        if not template:
            raise NotFoundError(detail="Template not found")

        return template


@router.get("/by-status/{status_filter}", response_model=list[TemplateListResponse])
async def get_templates_by_status(
    status_filter: str, uow: UnitOfWork = Depends(get_uow)
):
    """Get templates filtered by status."""
    async with uow:
        return await uow.templates.get_by_status(status_filter)
