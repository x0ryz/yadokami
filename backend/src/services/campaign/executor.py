from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    Campaign,
    CampaignStatus,
    get_utc_now,
)
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
from src.repositories.template import TemplateRepository
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService
from src.utils.template_renderer import render_template_params


class CampaignMessageExecutor:
    """Handles individual message sending within campaigns."""

    def __init__(
        self,
        session: AsyncSession,
        campaigns_repo: CampaignRepository,
        campaign_contacts_repo: CampaignContactRepository,
        contacts_repo: ContactRepository,
        template_repo: TemplateRepository,
        message_sender: MessageSenderService,
        notifier: NotificationService,
    ):
        self.session = session
        self.campaigns = campaigns_repo
        self.campaign_contacts = campaign_contacts_repo
        self.contacts = contacts_repo
        self.template_repo = template_repo
        self.sender = message_sender
        self.notifier = notifier

    async def send_message(
        self, campaign_id: UUID, link_id: UUID, contact_id: UUID
    ) -> bool:
        campaign = await self.campaigns.get_by_id_with_template(campaign_id)
        contact_link = await self.campaign_contacts.get_by_id(link_id)
        contact = await self.contacts.get_by_id(contact_id)

        if not all([campaign, contact_link, contact]):
            return False

        if not self._can_send_message(campaign, contact_link):
            return False

        template_name, body_text, lang_code = self._prepare_message_data(campaign)
        template_params = self._prepare_template_params(campaign, contact)

        # Determine message type: "template" if template_id exists, else "text"
        message_type = "template" if campaign.template_id else "text"

        try:
            message = await self.sender.send_to_contact(
                contact=contact,
                message_type=message_type,
                body=body_text,
                template_id=campaign.template_id,
                template_name=template_name,
                template_language_code=lang_code,
                template_parameters=template_params,
                is_campaign=True,
                phone_id=str(campaign.waba_phone_id)
                if campaign.waba_phone_id
                else None,
            )

            # Перевірка на невдачу (sender може повернути failed message замість raise)
            from src.models import MessageStatus

            if message.status == MessageStatus.FAILED:
                await self._handle_failed_message(campaign, contact_link, message)
                return False

            await self._handle_success_message(campaign, contact, contact_link, message)

            await self._notify_progress(campaign.id)

            return True

        except Exception as e:
            logger.error(f"Failed to send message to {contact_id}: {e}")
            await self.session.rollback()
            # Обробка критичної помилки (створення failed message, якщо його нема)
            # ... (тут твій код створення failed message) ...
            return False

    # --- Helpers ---

    def _can_send_message(self, campaign: Campaign, contact_link) -> bool:
        """Перевіряє, чи можна відправити повідомлення."""
        if campaign.status not in [CampaignStatus.RUNNING, CampaignStatus.PAUSED]:
            if campaign.status != CampaignStatus.RUNNING:
                return False

        if contact_link.message_id:
            return False

        return True

    def _prepare_message_data(
        self, campaign: Campaign
    ) -> tuple[str | None, str | None, str | None]:
        """Повертає (template_name, body_text, lang_code)"""
        if campaign.template_id and campaign.template:
            return campaign.template.name, None, campaign.template.language

        return None, None, None

    def _prepare_template_params(self, campaign, contact):
        """Виніс логіку параметрів в окремий метод для чистоти"""
        if not (campaign.template_id and campaign.variable_mapping):
            return None

        try:
            contact_data = {
                "name": contact.name,
                "phone_number": contact.phone_number,
                "custom_data": contact.custom_data or {},
            }
            return render_template_params(campaign.variable_mapping, contact_data)
        except ValueError as e:
            logger.warning(f"Template params error: {e}")
            return None

    async def _handle_failed_message(self, campaign, contact_link, message):
        """Обробка невдачі"""
        contact_link.message_id = message.id
        contact_link.retry_count += 1
        self.session.add(contact_link)

        await self.session.commit()

        # WebSocket notify
        await self.notifier.notify_message_status(
            message_id=message.id,
            status="failed",
            campaign_id=str(campaign.id),
            contact_id=str(contact_link.contact_id),
            error=message.error_message,
        )

    async def _handle_success_message(self, campaign, contact, contact_link, message):
        now = get_utc_now()

        contact_link.message_id = message.id
        contact_link.updated_at = now
        self.session.add(contact_link)

        contact.last_message_at = now
        self.session.add(contact)

        # Оновлюємо updated_at кампанії, але НЕ лічильники
        campaign.updated_at = now
        self.session.add(campaign)

        await self.session.commit()

        # WebSocket notify
        await self.notifier.notify_message_status(
            message_id=message.id,
            status="sent",
            campaign_id=str(campaign.id),
            contact_id=str(contact.id),
        )

    async def _notify_progress(self, campaign_id: UUID):
        """Відправляє оновлений прогрес (відсотки) через вебсокет."""
        # Отримуємо свіжу статистику
        stats = await self.campaigns.get_stats_by_id(campaign_id)
        if not stats:
            return

        # Рахуємо відсоток
        total = stats.get("total_contacts", 0)
        sent = stats.get("sent_count", 0)
        delivered = stats.get("delivered_count", 0)
        failed = stats.get("failed_count", 0)

        # Include SENT messages in processed count so progress updates immediately
        processed = sent + delivered + failed

        progress = 0.0
        if total > 0:
            progress = round((processed / total) * 100, 2)
        
        try:
            await self.notifier.notify_campaign_progress(
                campaign_id=str(campaign_id),
                progress_percent=progress,
                sent=sent,
                delivered=delivered,
                failed=failed,
                # Include total for frontend calculations
                total_contacts=total 
            )
        except Exception as e:
            logger.warning(f"Failed to notify progress for {campaign_id}: {e}")
