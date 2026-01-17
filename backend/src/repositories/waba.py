from sqlalchemy import select
from src.models import WabaAccount, WabaPhoneNumber
from src.repositories.base import BaseRepository


class WabaRepository(BaseRepository[WabaAccount]):
    def __init__(self, session):
        super().__init__(session, WabaAccount)

    async def get_credentials(self) -> WabaAccount | None:
        stmt = select(WabaAccount).limit(1)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_default_phone(self) -> WabaPhoneNumber | None:
        stmt = select(WabaPhoneNumber).limit(1)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_phone_id(self, phone_number_id: str) -> WabaPhoneNumber | None:
        stmt = select(WabaPhoneNumber).where(
            WabaPhoneNumber.phone_number_id == phone_number_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_waba_id(self, waba_id: str) -> WabaAccount | None:
        stmt = select(WabaAccount).where(WabaAccount.waba_id == waba_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_display_phone(self, phone: str) -> WabaPhoneNumber | None:
        stmt = select(WabaPhoneNumber).where(
            WabaPhoneNumber.display_phone_number == phone
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_accounts(self) -> list[WabaAccount]:
        return await self.get_all()

    async def get_all_phones(self) -> list[WabaPhoneNumber]:
        stmt = select(WabaPhoneNumber)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
