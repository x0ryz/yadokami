from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.meta import MetaClient
from src.models import Template, WabaAccount, WabaPhoneNumber, get_utc_now
from src.repositories.template import TemplateRepository
from src.repositories.waba import WabaPhoneRepository, WabaRepository


class SyncService:
    def __init__(self, session: AsyncSession, meta_client: MetaClient):
        self.session = session
        self.meta_client = meta_client
        self.waba = WabaRepository(session)
        self.waba_phones = WabaPhoneRepository(session)
        self.templates = TemplateRepository(session)

    async def sync_account_data(self):
        waba_account = await self.waba.get_credentials()
        if not waba_account:
            logger.warning("No WABA accounts found in the database.")
            return

        logger.info(f"Syncing WABA account ID: {waba_account.waba_id}")

        try:
            await self._sync_account_info(waba_account)
            await self._sync_phone_numbers(waba_account)
            await self._sync_templates(waba_account)

            await self.session.commit()
            logger.success(f"Synced account '{waba_account.name}' successfully")

        except Exception:
            logger.exception(f"Failed to sync WABA ID {waba_account.waba_id}")
            raise

    async def _sync_account_info(self, waba_account: WabaAccount):
        account_info = await self.meta_client.fetch_account_info(waba_account.waba_id)

        waba_account.name = str(account_info.get("name", ""))
        waba_account.account_review_status = account_info.get("account_review_status")
        waba_account.business_verification_status = account_info.get(
            "business_verification_status"
        )

        self.session.add(waba_account)
        await self.session.flush()

    async def _sync_phone_numbers(self, waba_account: WabaAccount):
        phones_data = await self.meta_client.fetch_phone_numbers(waba_account.waba_id)

        for item in phones_data.get("data", []):
            await self._upsert_phone_number(waba_account.id, item)

    async def _upsert_phone_number(self, waba_db_id, item: dict):
        phone_id = item.get("id")
        if not phone_id:
            return

        phone_obj = await self.waba_phones.get_by_phone_id(phone_id)

        if not phone_obj:
            phone_obj = WabaPhoneNumber(
                waba_id=waba_db_id,
                phone_number_id=phone_id,
                display_phone_number=str(item.get("display_phone_number", "")),
                status=item.get("code_verification_status"),
                quality_rating=str(item.get("quality_rating", "UNKNOWN")),
                messaging_limit_tier=item.get("messaging_limit_tier"),
            )
        else:
            phone_obj.status = item.get("code_verification_status")
            phone_obj.quality_rating = str(item.get("quality_rating", "UNKNOWN"))
            phone_obj.messaging_limit_tier = item.get("messaging_limit_tier")
            phone_obj.updated_at = get_utc_now()

        self.session.add(phone_obj)

    async def _sync_templates(self, waba_account: WabaAccount):
        logger.info(f"Syncing templates for WABA: {waba_account.name}")

        try:
            data = await self.meta_client.fetch_templates(waba_account.waba_id)

            for item in data.get("data", []):
                await self._upsert_template(waba_account.id, item)

            logger.success("Templates synced successfully")
        except Exception:
            logger.exception("Failed to sync templates")
            raise

    async def _upsert_template(self, waba_id, item: dict):
        meta_id = item.get("id")
        if not meta_id:
            return

        existing = await self.templates.get_by_meta_id(meta_id)

        status = str(item.get("status", "UNKNOWN"))
        components = item.get("components", [])

        if not existing:
            existing = Template(
                waba_id=waba_id,
                meta_template_id=meta_id,
                name=str(item.get("name", "")),
                language=str(item.get("language", "")),
                status=status,
                category=str(item.get("category", "")),
                components=components,
            )
        else:
            existing.status = status
            existing.components = components
            existing.updated_at = get_utc_now()

        self.session.add(existing)
