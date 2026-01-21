from sqlalchemy.ext.asyncio import AsyncSession

from src.models import get_utc_now
from src.repositories.template import TemplateRepository
from src.repositories.waba import WabaPhoneRepository, WabaRepository
from src.schemas import (
    MetaAccountReviewUpdate,
    MetaPhoneNumberQualityUpdate,
    MetaTemplateUpdate,
)
from src.services.notifications.service import NotificationService


class SystemEventHandler:
    """Handles system-level events like template updates, account reviews, and phone quality updates."""

    def __init__(self, session: AsyncSession, notifier: NotificationService):
        self.session = session
        self.notifier = notifier

        # Ініціалізуємо репозиторії
        self.templates = TemplateRepository(session)
        self.waba = WabaRepository(session)
        self.waba_phones = WabaPhoneRepository(session)

    async def handle_template_update(self, update: MetaTemplateUpdate):
        """Handle template status updates."""
        # Прибираємо async with uow
        template = await self.templates.get_by_meta_id(update.message_template_id)
        if template:
            template.status = update.event
            template.updated_at = get_utc_now()
            self.templates.add(template)

            await self.session.commit()

        # Notify after commit
        await self.notifier.notify_template_update(
            template_id=update.message_template_id,
            name=update.message_template_name,
            status=update.event,
            reason=update.reason,
        )

    async def handle_account_review(
        self, waba_id: str, update: MetaAccountReviewUpdate
    ):
        """Handle WABA account review status updates."""
        account = await self.waba.get_by_waba_id(waba_id)
        if account:
            account.account_review_status = update.decision
            self.waba.add(account)

            await self.session.commit()

        # Notify after commit
        await self.notifier.notify_waba_update(
            waba_id=waba_id, status=update.decision, event_type="REVIEW_UPDATE"
        )

    async def handle_phone_quality(self, update: MetaPhoneNumberQualityUpdate):
        """Handle phone number quality and messaging limit updates."""
        phone = await self.waba_phones.get_by_display_phone(update.display_phone_number)
        if phone:
            phone.messaging_limit_tier = update.current_limit
            if update.event == "FLAGGED":
                phone.quality_rating = "RED"
            elif update.event == "UNFLAGGED":
                phone.quality_rating = "GREEN"

            self.waba_phones.add(phone)
            await self.session.commit()

        # Notify after commit
        await self.notifier.notify_phone_update(
            phone_number=update.display_phone_number,
            event=update.event,
            current_limit=update.current_limit,
        )
