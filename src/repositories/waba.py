from sqlmodel import select

from src.models import WabaAccount, WabaPhoneNumber
from src.repositories.base import BaseRepository


class WabaRepository(BaseRepository[WabaAccount]):
    def __init__(self, session):
        super().__init__(session, WabaAccount)

    async def get_default_phone(self) -> WabaPhoneNumber | None:
        stmt = select(WabaPhoneNumber)
        return (await self.session.exec(stmt)).first()

    async def get_by_phone_id(self, phone_number_id: str) -> WabaPhoneNumber | None:
        stmt = select(WabaPhoneNumber).where(
            WabaPhoneNumber.phone_number_id == phone_number_id
        )
        return (await self.session.exec(stmt)).first()
