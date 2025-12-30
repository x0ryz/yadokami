from sqlmodel import select

from src.models import Template
from src.repositories.base import BaseRepository


class TemplateRepository(BaseRepository[Template]):
    def __init__(self, session):
        super().__init__(session, Template)

    async def get_active_by_id(self, template_id: str) -> Template | None:
        stmt = select(Template).where(
            Template.id == template_id, Template.status == "APPROVED"
        )
        return (await self.session.exec(stmt)).first()
