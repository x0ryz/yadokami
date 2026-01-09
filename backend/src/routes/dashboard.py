from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.database import get_session
from src.models import (
    Campaign,
    CampaignStatus,
    Contact,
    Message,
    MessageDirection,
    MessageStatus,
    WabaAccount,
    WabaPhoneNumber,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_stats(session: AsyncSession = Depends(get_session)):
    """
    Get overall system statistics for dashboard.

    Returns:
    - Total contacts
    - Total messages (sent/received)
    - Active campaigns
    - Recent activity metrics
    """
    # Total contacts
    stmt = select(func.count(Contact.id))
    total_contacts = await session.scalar(stmt)

    # Contacts with unread messages
    stmt = select(func.count(Contact.id)).where(Contact.unread_count > 0)
    unread_contacts = await session.scalar(stmt)

    # Total messages
    stmt = select(func.count(Message.id))
    total_messages = await session.scalar(stmt)

    # Messages by direction
    stmt = select(func.count(Message.id)).where(
        Message.direction == MessageDirection.OUTBOUND
    )
    sent_messages = await session.scalar(stmt)

    stmt = select(func.count(Message.id)).where(
        Message.direction == MessageDirection.INBOUND
    )
    received_messages = await session.scalar(stmt)

    # Campaigns stats
    stmt = select(func.count(Campaign.id))
    total_campaigns = await session.scalar(stmt)

    stmt = select(func.count(Campaign.id)).where(
        Campaign.status == CampaignStatus.RUNNING
    )
    active_campaigns = await session.scalar(stmt)

    stmt = select(func.count(Campaign.id)).where(
        Campaign.status == CampaignStatus.COMPLETED
    )
    completed_campaigns = await session.scalar(stmt)

    # Messages in last 24h
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    stmt = select(func.count(Message.id)).where(Message.created_at >= yesterday)
    messages_24h = await session.scalar(stmt)

    # Delivery rate
    stmt = select(func.count(Message.id)).where(
        Message.direction == MessageDirection.OUTBOUND,
        Message.status == MessageStatus.DELIVERED,
    )
    delivered_count = await session.scalar(stmt)

    delivery_rate = 0.0
    if sent_messages and sent_messages > 0:
        delivery_rate = (delivered_count / sent_messages) * 100

    return {
        "contacts": {
            "total": total_contacts or 0,
            "unread": unread_contacts or 0,
        },
        "messages": {
            "total": total_messages or 0,
            "sent": sent_messages or 0,
            "received": received_messages or 0,
            "last_24h": messages_24h or 0,
            "delivery_rate": round(delivery_rate, 2),
        },
        "campaigns": {
            "total": total_campaigns or 0,
            "active": active_campaigns or 0,
            "completed": completed_campaigns or 0,
        },
    }


@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 20, session: AsyncSession = Depends(get_session)
):
    """
    Get recent system activity.

    Returns latest messages and campaign events.
    """
    # Recent messages
    stmt = select(Message).order_by(Message.created_at.desc()).limit(limit)
    result = await session.exec(stmt)
    recent_messages = result.all()

    # Recent campaigns
    stmt = select(Campaign).order_by(Campaign.updated_at.desc()).limit(10)
    result = await session.exec(stmt)
    recent_campaigns = result.all()

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


@router.get("/charts/messages-timeline")
async def get_messages_timeline(
    days: int = 7, session: AsyncSession = Depends(get_session)
):
    """
    Get message statistics for the last N days.

    Returns daily message counts for charts.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = select(Message).where(Message.created_at >= start_date)
    result = await session.exec(stmt)
    messages = result.all()

    # Group by date
    daily_stats = {}
    for msg in messages:
        date_key = msg.created_at.date().isoformat()
        if date_key not in daily_stats:
            daily_stats[date_key] = {"sent": 0, "received": 0}

        if msg.direction == MessageDirection.OUTBOUND:
            daily_stats[date_key]["sent"] += 1
        else:
            daily_stats[date_key]["received"] += 1

    # Convert to list format for charts
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


@router.get("/waba-status")
async def get_waba_status(session: AsyncSession = Depends(get_session)):
    """
    Get WABA accounts and phone numbers status.

    Returns current data from database - fast response.
    Use /waba/sync endpoint to refresh data from Meta.
    """
    # Get all WABA accounts
    stmt = select(WabaAccount)
    result = await session.exec(stmt)
    accounts = result.all()

    # Get all phone numbers with relationships
    stmt = select(WabaPhoneNumber)
    result = await session.exec(stmt)
    phones = result.all()

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
