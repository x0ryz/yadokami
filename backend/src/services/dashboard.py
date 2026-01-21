from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CampaignStatus, MessageDirection
from src.repositories.campaign import CampaignRepository
from src.repositories.contact import ContactRepository
from src.repositories.message import MessageRepository
from src.repositories.waba import WabaPhoneRepository, WabaRepository


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

        self.contacts = ContactRepository(session)
        self.messages = MessageRepository(session)
        self.campaigns = CampaignRepository(session)
        self.waba = WabaRepository(session)
        self.waba_phones = WabaPhoneRepository(session)

    async def get_stats(self) -> dict:
        total_contacts = await self.contacts.count_all()
        unread_contacts = await self.contacts.count_unread()

        total_messages = await self.messages.count_all()
        sent_messages = await self.messages.count_by_direction(
            MessageDirection.OUTBOUND
        )
        received_messages = await self.messages.count_by_direction(
            MessageDirection.INBOUND
        )

        total_campaigns = await self.campaigns.count_total()
        active_campaigns = await self.campaigns.count_by_global_status(
            CampaignStatus.RUNNING
        )
        completed_campaigns = await self.campaigns.count_by_global_status(
            CampaignStatus.COMPLETED
        )

        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        messages_24h = await self.messages.count_recent(yesterday)

        delivered_count = await self.messages.count_delivered_outbound()

        delivery_rate = 0.0
        if sent_messages and sent_messages > 0:
            delivery_rate = (delivered_count / sent_messages) * 100

        return {
            "contacts": {
                "total": total_contacts,
                "unread": unread_contacts,
            },
            "messages": {
                "total": total_messages,
                "sent": sent_messages,
                "received": received_messages,
                "last_24h": messages_24h,
                "delivery_rate": round(delivery_rate, 2),
            },
            "campaigns": {
                "total": total_campaigns,
                "active": active_campaigns,
                "completed": completed_campaigns,
            },
        }

    async def get_recent_activity(self, limit: int) -> dict:
        recent_messages = await self.messages.get_recent(limit)
        recent_campaigns = await self.campaigns.get_recent(10)

        return {
            "messages": [
                {
                    "id": str(msg.id),
                    "direction": msg.direction,
                    "type": msg.message_type,
                    "status": msg.status,
                    "created_at": msg.created_at,
                }
                for msg in recent_messages
            ],
            "campaigns": [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "status": c.status,
                    "sent_count": c.sent_count,
                    "total_contacts": c.total_contacts,
                    "updated_at": c.updated_at,
                }
                for c in recent_campaigns
            ],
        }

    async def get_messages_timeline(self, days: int) -> list[dict]:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        messages = await self.messages.get_after(start_date)

        daily_stats = {}
        for msg in messages:
            date_key = msg.created_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {"sent": 0, "received": 0}

            if msg.direction == MessageDirection.OUTBOUND:
                daily_stats[date_key]["sent"] += 1
            else:
                daily_stats[date_key]["received"] += 1

        timeline = []
        for i in range(days):
            date = (datetime.now(timezone.utc) - timedelta(days=days - i - 1)).date()
            date_key = date.isoformat()
            timeline.append(
                {
                    "date": date_key,
                    "sent": daily_stats.get(date_key, {}).get("sent", 0),
                    "received": daily_stats.get(date_key, {}).get("received", 0),
                }
            )

        return timeline

    async def get_waba_status(self) -> dict:
        accounts = await self.waba.get_all_accounts()
        phones = await self.waba_phones.get_all_phones()

        return {
            "accounts": [
                {
                    "id": str(acc.id),
                    "waba_id": acc.waba_id,
                    "name": acc.name,
                    "account_review_status": acc.account_review_status,
                    "business_verification_status": acc.business_verification_status,
                }
                for acc in accounts
            ],
            "phone_numbers": [
                {
                    "id": str(phone.id),
                    "waba_id": str(phone.waba_id),
                    "phone_number_id": phone.phone_number_id,
                    "display_phone_number": phone.display_phone_number,
                    "status": phone.status,
                    "quality_rating": phone.quality_rating,
                    "messaging_limit_tier": phone.messaging_limit_tier,
                    "updated_at": phone.updated_at.isoformat()
                    if phone.updated_at
                    else None,
                }
                for phone in phones
            ],
        }
