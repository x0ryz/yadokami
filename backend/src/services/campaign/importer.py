import csv
import io
import re
from typing import BinaryIO
from uuid import UUID

import openpyxl
from loguru import logger

from src.core.uow import UnitOfWork
from src.models import CampaignContact, Contact, get_utc_now
from src.schemas import ContactImport, ContactImportResult


class ContactImportService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def _normalize_phone(self, phone: str) -> str | None:
        """
        Normalize phone number to E.164 format WITHOUT plus sign.
        Supports UA (380), PL (48), DE (49).

        Examples:
        - +380671234567 -> 380671234567
        - 0671234567 -> 380671234567 (UA local)
        - 48123456789 -> 48123456789 (PL)
        """
        if not phone:
            return None

        digits = re.sub(r"\D", "", phone)

        if digits.startswith("380") and len(digits) == 12:
            return digits

        if digits.startswith("48") and len(digits) == 11:
            return digits

        if digits.startswith("49") and 11 <= len(digits) <= 15:
            return digits

        if digits.startswith("0") and len(digits) == 10:
            return f"38{digits}"

        if len(digits) == 9:
            return f"380{digits}"

        return None

    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number format (digits only, 10-15 chars)"""
        if not phone:
            return False

        if not phone.isdigit():
            return False

        if len(phone) < 10 or len(phone) > 15:
            return False

        return True

    async def _get_or_create_contact(
        self, phone: str, name: str | None, tags: list[str], source: str
    ) -> Contact:
        """Get existing contact or create new one"""
        contact = await self.uow.contacts.get_by_phone(phone)

        if not contact:
            contact = Contact(
                phone_number=phone,
                name=name,
                tags=tags,
                source=source,
                created_at=get_utc_now(),
                updated_at=get_utc_now(),
            )
            self.uow.session.add(contact)
            await self.uow.session.flush()
            await self.uow.session.refresh(contact)
        else:
            # Update existing contact
            if name and not contact.name:
                contact.name = name

            # Merge tags
            if tags:
                existing_tags = set(contact.tags or [])
                new_tags = existing_tags.union(set(tags))
                contact.tags = list(new_tags)

            contact.updated_at = get_utc_now()
            self.uow.session.add(contact)

        return contact

    async def import_from_csv(
        self, campaign_id: UUID, file_content: bytes
    ) -> ContactImportResult:
        result = ContactImportResult(total=0, imported=0, skipped=0, errors=[])

        try:
            # Decode file
            text = file_content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))

            contacts_to_import: list[ContactImport] = []

            for row_num, row in enumerate(reader, start=2):
                result.total += 1

                try:
                    phone = row.get("phone_number", "").strip()
                    name = row.get("name", "").strip() or None
                    tags_str = row.get("tags", "").strip()

                    if not phone:
                        result.errors.append(f"Row {row_num}: Missing phone number")
                        result.skipped += 1
                        continue

                    # Normalize phone
                    normalized_phone = self._normalize_phone(phone)
                    if not normalized_phone:
                        result.errors.append(
                            f"Row {row_num}: Invalid phone format: {phone}"
                        )
                        result.skipped += 1
                        continue

                    # Validate phone
                    if not self._validate_phone(normalized_phone):
                        result.errors.append(
                            f"Row {row_num}: Phone validation failed: {normalized_phone}"
                        )
                        result.skipped += 1
                        continue

                    # Parse tags
                    tags = []
                    if tags_str:
                        tags = [
                            t.strip() for t in re.split(r"[;,]", tags_str) if t.strip()
                        ]

                    contacts_to_import.append(
                        ContactImport(
                            phone_number=normalized_phone, name=name, tags=tags
                        )
                    )

                except Exception as e:
                    result.errors.append(f"Row {row_num}: {str(e)}")
                    result.skipped += 1

            # Import contacts in batch
            result.imported = await self._import_contacts_batch(
                campaign_id, contacts_to_import
            )

            logger.info(
                f"CSV import completed: {result.imported}/{result.total} contacts"
            )

        except Exception as e:
            logger.error(f"CSV import failed: {e}")
            result.errors.append(f"File parsing error: {str(e)}")

        return result

    async def import_from_excel(
        self, campaign_id: UUID, file_content: bytes
    ) -> ContactImportResult:
        """
        Import contacts from Excel file (.xlsx, .xls).

        Expected columns: phone_number, name, tags
        First row must be headers.
        """
        result = ContactImportResult(total=0, imported=0, skipped=0, errors=[])

        try:
            # Load workbook
            workbook = openpyxl.load_workbook(io.BytesIO(file_content))
            sheet = workbook.active

            # Get headers from first row
            headers = []
            for cell in sheet[1]:
                headers.append(cell.value.lower().strip() if cell.value else "")

            # Find required columns
            if "phone_number" not in headers:
                result.errors.append("Missing required column: phone_number")
                return result

            phone_col = headers.index("phone_number")
            name_col = headers.index("name") if "name" in headers else None
            tags_col = headers.index("tags") if "tags" in headers else None

            contacts_to_import: list[ContactImport] = []

            # Process rows (skip header)
            for row_num, row in enumerate(sheet.iter_rows(min_row=2), start=2):
                result.total += 1

                try:
                    phone = (
                        str(row[phone_col].value).strip()
                        if row[phone_col].value
                        else ""
                    )
                    name = (
                        str(row[name_col].value).strip()
                        if name_col is not None and row[name_col].value
                        else None
                    )
                    tags_str = (
                        str(row[tags_col].value).strip()
                        if tags_col is not None and row[tags_col].value
                        else ""
                    )

                    if not phone:
                        result.errors.append(f"Row {row_num}: Missing phone number")
                        result.skipped += 1
                        continue

                    # Normalize phone
                    normalized_phone = self._normalize_phone(phone)
                    if not normalized_phone:
                        result.errors.append(
                            f"Row {row_num}: Invalid phone format: {phone}"
                        )
                        result.skipped += 1
                        continue

                    # Validate phone
                    if not self._validate_phone(normalized_phone):
                        result.errors.append(
                            f"Row {row_num}: Phone validation failed: {normalized_phone}"
                        )
                        result.skipped += 1
                        continue

                    # Parse tags
                    tags = []
                    if tags_str:
                        tags = [
                            t.strip() for t in re.split(r"[;,]", tags_str) if t.strip()
                        ]

                    contacts_to_import.append(
                        ContactImport(
                            phone_number=normalized_phone, name=name, tags=tags
                        )
                    )

                except Exception as e:
                    result.errors.append(f"Row {row_num}: {str(e)}")
                    result.skipped += 1

            # Import contacts in batch
            result.imported = await self._import_contacts_batch(
                campaign_id, contacts_to_import
            )

            logger.info(
                f"Excel import completed: {result.imported}/{result.total} contacts"
            )

        except Exception as e:
            logger.error(f"Excel import failed: {e}")
            result.errors.append(f"File parsing error: {str(e)}")

        return result

    async def _import_contacts_batch(
        self, campaign_id: UUID, contacts: list[ContactImport]
    ) -> int:
        """Import list of contacts and link to campaign"""
        imported_count = 0

        # Get campaign
        campaign = await self.uow.campaigns.get_by_id(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        for contact_data in contacts:
            try:
                # Check if already in campaign
                contact = await self.uow.contacts.get_by_phone(
                    contact_data.phone_number
                )

                if contact:
                    exists = await self.uow.campaign_contacts.exists_for_contact(
                        campaign_id, contact.id
                    )
                    if exists:
                        continue  # Skip duplicate

                # Get or create contact
                contact = await self._get_or_create_contact(
                    phone=contact_data.phone_number,
                    name=contact_data.name,
                    tags=contact_data.tags,
                    source="import_csv",
                )

                # Create campaign link
                link = CampaignContact(
                    campaign_id=campaign_id,
                    contact_id=contact.id,
                    created_at=get_utc_now(),
                    updated_at=get_utc_now(),
                )
                self.uow.session.add(link)

                imported_count += 1

            except Exception as e:
                logger.error(
                    f"Failed to import contact {contact_data.phone_number}: {e}"
                )

        # Update campaign total
        campaign.total_contacts = await self.uow.campaign_contacts.count_all(
            campaign_id
        )
        campaign.updated_at = get_utc_now()
        self.uow.session.add(campaign)

        await self.uow.session.flush()

        return imported_count

    async def add_contacts_manual(
        self, campaign_id: UUID, contacts: list[ContactImport]
    ) -> ContactImportResult:
        """
        Add contacts manually via API (not from file).
        """
        result = ContactImportResult(
            total=len(contacts), imported=0, skipped=0, errors=[]
        )

        try:
            # Validate and normalize
            valid_contacts = []
            for idx, contact in enumerate(contacts):
                normalized_phone = self._normalize_phone(contact.phone_number)

                if not normalized_phone or not self._validate_phone(normalized_phone):
                    result.errors.append(
                        f"Contact {idx + 1}: Invalid phone {contact.phone_number}"
                    )
                    result.skipped += 1
                    continue

                valid_contacts.append(
                    ContactImport(
                        phone_number=normalized_phone,
                        name=contact.name,
                        tags=contact.tags,
                    )
                )

            # Import batch
            result.imported = await self._import_contacts_batch(
                campaign_id, valid_contacts
            )

            logger.info(
                f"Manual import: {result.imported}/{result.total} contacts added"
            )

        except Exception as e:
            logger.error(f"Manual import failed: {e}")
            result.errors.append(str(e))

        return result
