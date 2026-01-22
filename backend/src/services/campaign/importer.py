import io
import re
from uuid import UUID

import pandas as pd
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CampaignContact, Contact, get_utc_now
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
from src.schemas import ContactImport, ContactImportResult


class ContactImportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.campaigns = CampaignRepository(session)
        self.contacts = ContactRepository(session)
        self.campaign_contacts = CampaignContactRepository(session)

    def _normalize_phone(self, phone: any) -> str | None:
        if pd.isna(phone) or phone == "":
            return None

        digits = re.sub(r"\D", "", str(phone))

        if digits.startswith("380") and len(digits) == 12:
            return digits
        if digits.startswith("0") and len(digits) == 10:
            return f"38{digits}"
        if len(digits) == 9:
            return f"380{digits}"

        if 10 <= len(digits) <= 15:
            return digits

        return None

    def _find_column(self, df: pd.DataFrame, candidates: list[str]) -> str | None:
        df_cols = [str(c).lower() for c in df.columns]
        for cand in candidates:
            if cand.lower() in df_cols:
                return df.columns[df_cols.index(cand.lower())]
        return None

    async def import_file(
        self, campaign_id: UUID, file_content: bytes, filename: str
    ) -> ContactImportResult:
        result = ContactImportResult(total=0, imported=0, skipped=0, errors=[])

        try:
            if filename.lower().endswith(".csv"):
                df = pd.read_csv(io.BytesIO(file_content))
            elif filename.lower().endswith((".xls", ".xlsx")):
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                result.errors.append(
                    "Unsupported file format. Use CSV or Excel.")
                return result

            result.total = len(df)

            phone_col = self._find_column(
                df, ["phone", "phone_number", "телефон", "номер"]
            )
            name_col = self._find_column(
                df, ["name", "full_name", "ім'я", "фио"])
            link_col = self._find_column(
                df, ["link", "url", "profile", "силка", "посилання"]
            )

            if not phone_col:
                result.errors.append("Не знайдено колонку з телефоном")
                return result

            df = df.dropna(subset=[phone_col])

            contacts_data = []
            for _, row in df.iterrows():
                phone = self._normalize_phone(row[phone_col])
                if not phone:
                    result.skipped += 1
                    continue

                name = (
                    str(row[name_col]).strip()
                    if name_col and pd.notna(row[name_col])
                    else None
                )

                custom_data = {}
                if link_col and pd.notna(row[link_col]):
                    custom_data["link"] = str(row[link_col]).strip()

                # Додаємо всі інші колонки в custom_data
                for col in df.columns:
                    if col not in [phone_col, name_col, link_col] and pd.notna(row[col]):
                        custom_data[str(col)] = str(row[col]).strip()

                contacts_data.append(
                    {"phone": phone, "name": name, "custom_data": custom_data})

            unique_contacts = {c["phone"]: c for c in contacts_data}.values()

            result.imported = await self._save_contacts_batch(
                campaign_id, list(unique_contacts)
            )
            result.skipped += result.total - result.imported

        except Exception as e:
            logger.error(f"Import failed: {e}")
            result.errors.append(f"System error: {str(e)}")

        return result

    async def add_contacts_manual(
        self, campaign_id: UUID, contacts: list[ContactImport]
    ) -> ContactImportResult:
        contacts_data = []
        skipped = 0

        for contact in contacts:
            phone = self._normalize_phone(contact.phone_number)
            if not phone:
                skipped += 1
                continue

            contacts_data.append(
                {
                    "phone": phone,
                    "name": contact.name,
                    "custom_data": contact.custom_data if contact.custom_data else {},
                }
            )

        imported = await self._save_contacts_batch(campaign_id, contacts_data)

        return ContactImportResult(
            total=len(contacts),
            imported=imported,
            skipped=len(contacts) - imported,
            errors=[],
        )

    async def _save_contacts_batch(
        self, campaign_id: UUID, contacts_data: list[dict]
    ) -> int:
        imported_count = 0
        campaign = await self.campaigns.get_by_id(campaign_id)

        if not campaign:
            logger.error(f"Campaign {campaign_id} not found during import")
            return 0

        for data in contacts_data:
            try:
                contact = await self.contacts.get_by_phone(data["phone"])

                if not contact:
                    contact = Contact(
                        phone_number=data["phone"],
                        name=data["name"],
                        custom_data=data.get("custom_data", {}),
                        source="import",
                        created_at=get_utc_now(),
                        updated_at=get_utc_now(),
                    )
                    self.session.add(contact)
                    await self.session.flush()
                else:
                    updated = False
                    if data["name"] and not contact.name:
                        contact.name = data["name"]
                        updated = True

                    # Оновлюємо custom_data якщо є нові дані
                    new_custom_data = data.get("custom_data", {})
                    if new_custom_data:
                        contact.custom_data = {
                            **contact.custom_data, **new_custom_data}
                        updated = True

                    if updated:
                        contact.updated_at = get_utc_now()
                        self.session.add(contact)

                exists = await self.campaign_contacts.exists_for_contact(
                    campaign_id, contact.id
                )

                if not exists:
                    link = CampaignContact(
                        campaign_id=campaign_id,
                        contact_id=contact.id,
                        created_at=get_utc_now(),
                        updated_at=get_utc_now(),
                    )
                    self.session.add(link)
                    imported_count += 1

            except Exception as e:
                logger.error(f"Save contact error: {e}")

        await self.session.flush()

        campaign.total_contacts = await self.campaign_contacts.count_all(campaign_id)
        campaign.updated_at = get_utc_now()
        self.session.add(campaign)

        await self.session.commit()
        return imported_count
