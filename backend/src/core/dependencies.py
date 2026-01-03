from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.database import get_session
from src.core.uow import UnitOfWork


async def get_uow(session: AsyncSession = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(session_factory=lambda: session)
