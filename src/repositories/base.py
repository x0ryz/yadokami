from typing import Generic, Type, TypeVar
from uuid import UUID

from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model

    async def get_by_id(self, id: UUID) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def get_all(self) -> list[ModelType]:
        stmt = select(self.model)
        return (await self.session.exec(stmt)).all()

    def add(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        return obj

    async def delete(self, id: UUID) -> None:
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
