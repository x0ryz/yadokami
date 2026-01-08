from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.tags import Tag


class TagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> Tag:
        tag = Tag(**data)
        self.session.add(tag)
        return tag

    async def get_all(self) -> Sequence[Tag]:
        query = select(Tag).order_by(Tag.name)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_id(self, tag_id: UUID) -> Tag | None:
        return await self.session.get(Tag, tag_id)

    async def get_by_ids(self, tag_ids: list[UUID]) -> Sequence[Tag]:
        if not tag_ids:
            return []
        query = select(Tag).where(Tag.id.in_(tag_ids))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def delete(self, tag_id: UUID) -> None:
        tag = await self.get_by_id(tag_id)
        if tag:
            await self.session.delete(tag)
