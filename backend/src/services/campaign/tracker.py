import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CampaignDeliveryStatus, MessageStatus, get_utc_now
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.message import MessageRepository


@dataclass
class CampaignProgressTracker:
    """
    In-memory трекер для воркера.
    Використовується Sender-сервісом для розрахунку ETA та швидкості в реальному часі.
    """

    campaign_id: uuid.UUID
    start_time: datetime = field(default_factory=get_utc_now)
    batches_processed: int = 0
    total_sent: int = 0
    total_failed: int = 0

    def increment_sent(self):
        self.total_sent += 1

    def increment_failed(self):
        self.total_failed += 1

    def increment_batch(self):
        self.batches_processed += 1

    def calculate_rate(self) -> float:
        """Повідомлень на хвилину."""
        elapsed_seconds = (get_utc_now() - self.start_time).total_seconds()
        if elapsed_seconds <= 0 or self.total_sent <= 0:
            return 0.0
        return (self.total_sent / elapsed_seconds) * 60

    def estimate_completion(self, remaining_contacts: int) -> str | None:
        """ISO timestamp завершення."""
        rate_per_minute = self.calculate_rate()
        if rate_per_minute <= 0:
            return None

        eta_minutes = remaining_contacts / rate_per_minute
        completion_time = get_utc_now() + timedelta(minutes=eta_minutes)
        return completion_time.isoformat()

    def get_elapsed_time(self) -> float:
        return (get_utc_now() - self.start_time).total_seconds()

    def to_dict(self) -> dict:
        return {
            "campaign_id": str(self.campaign_id),
            "batches_processed": self.batches_processed,
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "rate_per_minute": round(self.calculate_rate(), 2),
            "elapsed_seconds": round(self.get_elapsed_time(), 2),
            "started_at": self.start_time.isoformat(),
        }


class CampaignTrackerService:
    """
    Сервіс для оновлення життєвого циклу кампанії в БД.
    Обробляє: Sent -> Delivered -> Read -> Replied -> Failed.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.campaigns = CampaignRepository(session)
        self.campaign_contacts = CampaignContactRepository(session)
        # MessageRepository потрібен для пошуку кампанії при відповіді
        self.messages = MessageRepository(session)

    async def update_on_status_change(
        self, message_id: uuid.UUID, new_status: MessageStatus
    ) -> None:
        """
        Викликається з StatusHandler (webhook).
        Оновлює лічильники delivered/read/failed.
        """
        campaign_link = await self.campaign_contacts.get_by_message_id(message_id)

        if not campaign_link:
            return  # Це не повідомлення кампанії

        # Якщо вже відповіли - ігноруємо інші статуси (наприклад, прочитав після відповіді)
        if campaign_link.status == CampaignDeliveryStatus.REPLIED:
            return

        campaign = await self.campaigns.get_by_id(campaign_link.campaign_id)
        if not campaign:
            logger.warning(f"Campaign {campaign_link.campaign_id} not found")
            return

        # Логіка зміни статусів
        if new_status == MessageStatus.DELIVERED:
            await self._handle_delivered(campaign, campaign_link)
        elif new_status == MessageStatus.READ:
            await self._handle_read(campaign, campaign_link)
        elif new_status == MessageStatus.FAILED:
            await self._handle_failed(campaign, campaign_link)

        self.campaigns.add(campaign)
        self.campaign_contacts.add(campaign_link)

        # Робимо коміт тут, бо це атомарна дія реакції на вебхук
        await self.session.commit()

    async def handle_reply(self, contact_id: uuid.UUID) -> None:
        """
        Викликається з IncomingMessageHandler (webhook).
        Фіксує факт відповіді на кампанію.
        """
        # Знаходимо останнє повідомлення кампанії для цього контакту
        latest_campaign_msg = (
            await self.messages.get_latest_campaign_message_for_contact(contact_id)
        )

        if not latest_campaign_msg:
            return

        campaign_link = await self.campaign_contacts.get_by_message_id(
            latest_campaign_msg.id
        )

        if not campaign_link or campaign_link.status == CampaignDeliveryStatus.REPLIED:
            return

        campaign = await self.campaigns.get_by_id(campaign_link.campaign_id)
        if not campaign:
            return

        # Логіка Reply:
        campaign.replied_count += 1

        # Декрементуємо попередній статус, щоб статистика "билася"
        if campaign_link.status == CampaignDeliveryStatus.READ:
            campaign.read_count = max(0, campaign.read_count - 1)
        elif campaign_link.status == CampaignDeliveryStatus.DELIVERED:
            campaign.delivered_count = max(0, campaign.delivered_count - 1)
        elif campaign_link.status == CampaignDeliveryStatus.SENT:
            campaign.sent_count = max(0, campaign.sent_count - 1)

        campaign_link.status = CampaignDeliveryStatus.REPLIED

        self.campaigns.add(campaign)
        self.campaign_contacts.add(campaign_link)

        # Комітимо зміни
        await self.session.commit()

    # --- Internal Helpers ---

    async def _handle_delivered(self, campaign, campaign_link):
        if campaign_link.status in [
            CampaignDeliveryStatus.READ,
            CampaignDeliveryStatus.FAILED,
            CampaignDeliveryStatus.REPLIED,
        ]:
            return

        campaign_link.status = CampaignDeliveryStatus.DELIVERED
        campaign.delivered_count += 1
        # Якщо було Sent - зменшуємо, бо воно перейшло в Delivered
        campaign.sent_count = max(0, campaign.sent_count - 1)

    async def _handle_read(self, campaign, campaign_link):
        if campaign_link.status == CampaignDeliveryStatus.READ:
            return

        campaign_link.status = CampaignDeliveryStatus.READ
        campaign.read_count += 1
        # Зазвичай перехід йде Delivered -> Read
        campaign.delivered_count = max(0, campaign.delivered_count - 1)

    async def _handle_failed(self, campaign, campaign_link):
        if campaign_link.status == CampaignDeliveryStatus.FAILED:
            return

        campaign_link.status = CampaignDeliveryStatus.FAILED
        campaign.failed_count += 1
        # Тут ми не декрементуємо Sent/Delivered, бо не знаємо попереднього стану напевно,
        # або вважаємо Failed окремим фінальним статусом.
