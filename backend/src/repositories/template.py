from uuid import UUID

from sqlalchemy import select, update
from src.models import Template
from src.models import get_utc_now
from src.repositories.base import BaseRepository


class TemplateRepository(BaseRepository[Template]):
    def __init__(self, session):
        super().__init__(session, Template)

    async def get_active_by_id(self, template_id: str) -> Template | None:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.status == "APPROVED",
            Template.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_meta_id(
        self, meta_id: str, include_deleted: bool = False
    ) -> Template | None:
        """Get template by Meta ID. By default excludes deleted templates."""
        stmt = select(Template).where(Template.meta_template_id == meta_id)
        if not include_deleted:
            stmt = stmt.where(Template.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_sorted(self, include_deleted: bool = False) -> list[Template]:
        """Get all templates sorted by name. By default excludes deleted templates."""
        stmt = select(Template)
        if not include_deleted:
            stmt = stmt.where(Template.is_deleted == False)
        stmt = stmt.order_by(Template.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> list[Template]:
        stmt = select(Template).where(
            Template.status == status.upper(), Template.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_by_waba_id(self, waba_id: UUID) -> list[Template]:
        """Get all templates (including deleted) for a specific WABA account."""
        stmt = select(Template).where(Template.waba_id == waba_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def soft_delete_by_meta_ids(self, meta_ids: list[str]) -> int:
        """Soft delete templates by their Meta template IDs. Returns count of deleted templates."""
        if not meta_ids:
            return 0
        stmt = (
            update(Template)
            .where(Template.meta_template_id.in_(meta_ids))
            .values(is_deleted=True, updated_at=get_utc_now())
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def restore_by_meta_ids(self, meta_ids: list[str]) -> int:
        """Restore soft-deleted templates by their Meta template IDs."""
        if not meta_ids:
            return 0
        stmt = (
            update(Template)
            .where(Template.meta_template_id.in_(meta_ids))
            .values(is_deleted=False, updated_at=get_utc_now())
        )
        result = await self.session.execute(stmt)
        return result.rowcount
