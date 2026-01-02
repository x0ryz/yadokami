from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.database import get_session
from src.core.exceptions import NotFoundError
from src.models import Template

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=list[Template])
async def list_templates(session: AsyncSession = Depends(get_session)):
    """
    Get all message templates.

    Returns templates synced from Meta WhatsApp Business API.
    """
    stmt = select(Template).order_by(Template.name)
    result = await session.exec(stmt)
    templates = result.all()
    return templates


@router.get("/{template_id}", response_model=Template)
async def get_template(template_id: UUID, session: AsyncSession = Depends(get_session)):
    """
    Get specific template by ID.
    """
    template = await session.get(Template, template_id)

    if not template:
        raise NotFoundError(detail="Template not found")

    return template


@router.get("/by-status/{status_filter}")
async def get_templates_by_status(
    status_filter: str, session: AsyncSession = Depends(get_session)
):
    """
    Get templates filtered by status.

    - **APPROVED**: Ready to use
    - **PENDING**: Awaiting approval
    - **REJECTED**: Rejected by Meta
    """
    stmt = select(Template).where(Template.status == status_filter.upper())
    result = await session.exec(stmt)
    templates = result.all()
    return templates
