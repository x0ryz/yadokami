from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_session
from src.core.exceptions import NotFoundError
from src.repositories.template import TemplateRepository
from src.schemas import TemplateListResponse, TemplateResponse

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=list[TemplateListResponse])
async def list_templates(
    show_deleted: bool = False, session: AsyncSession = Depends(get_session)
):
    """
    Get all message templates.

    Returns templates synced from Meta WhatsApp Business API.
    By default excludes deleted templates. Set show_deleted=true to include them.
    """
    return await TemplateRepository(session).get_all_sorted(include_deleted=show_deleted)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: UUID, session: AsyncSession = Depends(get_session)):
    """
    Get specific template by ID.
    """
    template = await TemplateRepository(session).get_by_id(template_id)

    if not template:
        raise NotFoundError(detail="Template not found")

    return template


@router.get("/by-status/{status_filter}", response_model=list[TemplateListResponse])
async def get_templates_by_status(
    status_filter: str, session: AsyncSession = Depends(get_session)
):
    """Get templates filtered by status."""
    return await TemplateRepository(session).get_by_status(status_filter)
