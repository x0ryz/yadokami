from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.clients.meta import MetaClient
from src.models import Template, WabaAccount, WabaPhoneNumber, get_utc_now


class SyncService:
    def __init__(self, session: AsyncSession, meta_client: MetaClient):
        self.session = session
        self.meta_client = meta_client

    async def sync_account_data(self):
        stmt = select(WabaAccount)
        waba_account = (await self.session.exec(stmt)).first()

        if not waba_account:
            logger.warning("No WABA accounts found in the database.")
            return

        current_waba_id = waba_account.waba_id
        logger.info(f"Syncing WABA account ID: {current_waba_id}")

        try:
            account_info = await self.meta_client.fetch_account_info(current_waba_id)

            waba_account.name = account_info.get("name")
            waba_account.account_review_status = account_info.get(
                "account_review_status"
            )
            waba_account.business_verification_status = account_info.get(
                "business_verification_status"
            )

            self.session.add(waba_account)
            await self.session.commit()
            await self.session.refresh(waba_account)

            phones_data = await self.meta_client.fetch_phone_numbers(current_waba_id)

            for item in phones_data.get("data", []):
                await self._upsert_phone_number(waba_account.id, item)

            await self.session.commit()

            await self._sync_templates(waba_account)
            logger.success(f"Synced account '{waba_account.name}' and its phones.")

        except Exception as e:
            logger.exception(f"Failed to sync WABA ID {current_waba_id}")

    async def _upsert_phone_number(self, waba_db_id, item: dict):
        """Helper for creating or updating a phone number"""
        p_id = item.get("id")

        stmt_phone = select(WabaPhoneNumber).where(
            WabaPhoneNumber.phone_number_id == p_id
        )
        res_phone = await self.session.exec(stmt_phone)
        phone_obj = res_phone.first()

        if not phone_obj:
            phone_obj = WabaPhoneNumber(
                waba_id=waba_db_id,
                phone_number_id=p_id,
                display_phone_number=item.get("display_phone_number"),
                status=item.get("code_verification_status"),
                quality_rating=item.get("quality_rating"),
                messaging_limit_tier=item.get("messaging_limit_tier"),
            )
        else:
            phone_obj.status = item.get("code_verification_status")
            phone_obj.quality_rating = item.get("quality_rating")
            phone_obj.messaging_limit_tier = item.get("messaging_limit_tier")
            phone_obj.updated_at = get_utc_now()

        self.session.add(phone_obj)

    async def _sync_templates(self, waba_account: WabaAccount):
        logger.info(f"Syncing templates for WABA: {waba_account.name}")

        try:
            data = await self.meta_client.fetch_templates(waba_account.waba_id)

            for item in data.get("data", []):
                meta_id = item.get("id")

                stmt = select(Template).where(Template.meta_template_id == meta_id)
                existing = (await self.session.exec(stmt)).first()

                if not existing:
                    existing = Template(
                        waba_id=waba_account.id,
                        meta_template_id=meta_id,
                        name=item.get("name"),
                        language=item.get("language"),
                        status=item.get("status"),
                        category=item.get("category"),
                        components=item.get("components", []),
                    )
                else:
                    existing.status = item.get("status")
                    existing.components = item.get("components", [])
                    existing.updated_at = get_utc_now()

                self.session.add(existing)

            await self.session.commit()
            logger.success("Templates synced successfully")

        except Exception as e:
            logger.exception("Failed to sync templates")
