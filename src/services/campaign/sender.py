# src/services/campaign/sender_enhanced.py
"""
Enhanced Campaign Sender with comprehensive WebSocket event notifications.
"""

from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from uuid import UUID

from loguru import logger

from src.clients.meta import MetaClient
from src.core.uow import UnitOfWork
from src.models import (
    Campaign,
    CampaignStatus,
    Contact,
    ContactStatus,
    MessageDirection,
    MessageStatus,
    get_utc_now,
)
from src.services.websocket import (
    BatchProgressEvent,
    CampaignProgressEvent,
    CampaignStatusEvent,
    MessageStatusEvent,
)


class CampaignSenderService:
    """
    Campaign sender with rich real-time event notifications.

    Sends WebSocket updates for:
    - Campaign status changes
    - Progress updates with detailed stats
    - Batch processing progress
    - Individual message status
    - Rate limiting info
    - Error notifications
    """

    def __init__(
        self,
        uow: UnitOfWork,
        meta_client: MetaClient,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.uow = uow
        self.meta_client = meta_client
        self.notifier = notifier

        # Track batch statistics
        self.batch_stats = {}
        self.start_time = None

    async def _notify_event(self, event):
        """Send typed event notification"""
        if self.notifier:
            await self.notifier(event.to_dict())

    async def start_campaign(self, campaign_id: UUID):
        """Start campaign with status notification"""
        async with self.uow:
            campaign = await self.uow.campaigns.get_by_id_with_template(campaign_id)

            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")

            if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
                raise ValueError(f"Cannot start campaign in {campaign.status} status")

            if campaign.total_contacts == 0:
                raise ValueError("Cannot start campaign with no contacts")

            # Update status
            now = get_utc_now()
            campaign.status = CampaignStatus.RUNNING
            campaign.started_at = now
            campaign.updated_at = now
            self.uow.session.add(campaign)

            self.start_time = now
            self.batch_stats[str(campaign_id)] = {
                "batches_processed": 0,
                "total_sent": 0,
                "total_failed": 0,
                "start_time": now,
            }

            logger.info(f"Campaign {campaign_id} started")

            # Send detailed start notification
            await self._notify_event(
                CampaignStatusEvent(
                    campaign_id=campaign_id,
                    status="RUNNING",
                    name=campaign.name,
                    total_contacts=campaign.total_contacts,
                    message_type=campaign.message_type,
                    started_at=now.isoformat(),
                )
            )

            # Initial progress
            await self._notify_progress(campaign)

            await self.uow.commit()

    async def send_single_message(
        self, campaign_id: UUID, link_id: UUID, contact_id: UUID
    ):
        """
        Send message with detailed status notifications.
        """
        try:
            async with self.uow:
                campaign = await self.uow.campaigns.get_by_id_with_template(campaign_id)
                contact_link = await self.uow.campaign_contacts.get_by_id(link_id)
                contact = await self.uow.contacts.get_by_id(contact_id)

                if not campaign or not contact_link or not contact:
                    logger.warning(f"Data missing for send task: link {link_id}")
                    return

                if campaign.status != CampaignStatus.RUNNING:
                    logger.info(
                        f"Skipping contact {contact_id}: Campaign is {campaign.status}"
                    )
                    return

                if contact_link.status == ContactStatus.SENT:
                    logger.warning(f"Contact {contact_id} already sent")
                    return

                waba_phone = await self.uow.waba.get_default_phone()
                if not waba_phone:
                    await self._mark_as_failed(
                        contact_link, campaign, "No WABA phone available"
                    )
                    return

                body_text = campaign.message_body
                if campaign.message_type == "template" and campaign.template:
                    body_text = campaign.template.name

                message = await self.uow.messages.create(
                    auto_flush=True,
                    waba_phone_id=waba_phone.id,
                    contact_id=contact.id,
                    direction=MessageDirection.OUTBOUND,
                    status=MessageStatus.PENDING,
                    message_type=campaign.message_type,
                    body=body_text,
                    template_id=campaign.template_id,
                )

                payload = self._build_whatsapp_payload(campaign, contact)

                # Send via Meta API
                result = await self.meta_client.send_message(
                    waba_phone.phone_number_id, payload
                )

                wamid = result.get("messages", [{}])[0].get("id")

                if wamid:
                    now = get_utc_now()

                    # Update message
                    message.wamid = wamid
                    message.status = MessageStatus.SENT
                    self.uow.session.add(message)

                    # Update campaign contact
                    contact_link.status = ContactStatus.SENT
                    contact_link.message_id = message.id
                    contact_link.updated_at = now
                    self.uow.session.add(contact_link)

                    # Update contact
                    contact.last_message_at = now
                    contact.status = ContactStatus.SENT
                    contact.updated_at = now
                    self.uow.session.add(contact)

                    # Update campaign stats
                    campaign.sent_count += 1
                    campaign.updated_at = now
                    self.uow.session.add(campaign)

                    await self.uow.commit()

                    logger.info(
                        f"✓ Message sent to {contact.phone_number}, WAMID: {wamid}"
                    )

                    # Notify message sent
                    await self._notify_event(
                        MessageStatusEvent(
                            message_id=message.id,
                            wamid=wamid,
                            status="sent",
                            campaign_id=str(campaign.id),
                            contact_id=str(contact.id),
                            phone=contact.phone_number,
                            contact_name=contact.name,
                        )
                    )

                    # Update batch stats
                    if str(campaign_id) in self.batch_stats:
                        self.batch_stats[str(campaign_id)]["total_sent"] += 1

                    # Progress update (every message for real-time feel)
                    await self._notify_progress(campaign)

                else:
                    raise Exception("No WAMID in Meta response")

        except Exception as e:
            logger.exception(f"Failed to send to contact {contact_id}")

            async with self.uow:
                contact_link = await self.uow.campaign_contacts.get_by_id(link_id)
                campaign = await self.uow.campaigns.get_by_id(campaign_id)

                if contact_link and campaign:
                    await self._mark_as_failed(contact_link, campaign, str(e))

                    if str(campaign_id) in self.batch_stats:
                        self.batch_stats[str(campaign_id)]["total_failed"] += 1

        await self._check_campaign_completion(campaign_id)

    async def _mark_as_failed(self, link, campaign, error_msg: str):
        """Mark contact as failed with error notification"""
        link.status = ContactStatus.FAILED
        link.error_message = error_msg[:500]
        link.retry_count += 1
        link.updated_at = get_utc_now()
        self.uow.session.add(link)

        campaign.failed_count += 1
        campaign.updated_at = get_utc_now()
        self.uow.session.add(campaign)

        await self.uow.commit()

        # Notify failure
        await self._notify_event(
            MessageStatusEvent(
                message_id=link.message_id or link.id,
                wamid="",
                status="failed",
                campaign_id=str(campaign.id),
                contact_id=str(link.contact_id),
                error=error_msg,
                retry_count=link.retry_count,
            )
        )

    def _build_whatsapp_payload(self, campaign: Campaign, contact: Contact) -> dict:
        """Build Meta API payload"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": contact.phone_number,
            "type": campaign.message_type,
        }

        if campaign.message_type == "text":
            payload["text"] = {"body": campaign.message_body}

        elif campaign.message_type == "template":
            if not campaign.template:
                raise ValueError("Template not found for campaign")

            payload["template"] = {
                "name": campaign.template.name,
                "language": {"code": campaign.template.language},
            }

        return payload

    async def _notify_progress(self, campaign: Campaign):
        """Send detailed progress notification"""
        progress = 0.0
        if campaign.total_contacts > 0:
            progress = (campaign.sent_count / campaign.total_contacts) * 100

        # Calculate estimated completion
        estimated_completion = None
        current_rate = 0.0

        stats = self.batch_stats.get(str(campaign.id))
        if stats and stats["start_time"]:
            elapsed = (get_utc_now() - stats["start_time"]).total_seconds()
            if elapsed > 0 and campaign.sent_count > 0:
                current_rate = (campaign.sent_count / elapsed) * 60  # per minute

                remaining = campaign.total_contacts - campaign.sent_count
                if current_rate > 0:
                    eta_seconds = remaining / (current_rate / 60)
                    estimated_completion = (
                        get_utc_now() + datetime.timedelta(seconds=eta_seconds)
                    ).isoformat()

        pending = campaign.total_contacts - campaign.sent_count - campaign.failed_count

        await self._notify_event(
            CampaignProgressEvent(
                campaign_id=campaign.id,
                total=campaign.total_contacts,
                sent=campaign.sent_count,
                delivered=campaign.delivered_count,
                read=0,  # Can be updated from status webhooks
                failed=campaign.failed_count,
                pending=pending,
                progress_percent=round(progress, 2),
                estimated_completion=estimated_completion,
                current_rate=round(current_rate, 2),
            )
        )

    async def _check_campaign_completion(self, campaign_id: UUID):
        """Check and notify campaign completion"""
        async with self.uow:
            campaign = await self.uow.campaigns.get_by_id(campaign_id)

            if not campaign or campaign.status != CampaignStatus.RUNNING:
                return

            remaining = await self.uow.campaign_contacts.get_sendable_contacts(
                campaign_id, limit=1
            )

            if not remaining:
                now = get_utc_now()
                campaign.status = CampaignStatus.COMPLETED
                campaign.completed_at = now
                campaign.updated_at = now
                self.uow.session.add(campaign)
                await self.uow.commit()

                # Calculate final stats
                duration = None
                if campaign.started_at:
                    duration = (now - campaign.started_at).total_seconds()

                logger.info(f"Campaign {campaign_id} completed")

                await self._notify_event(
                    CampaignStatusEvent(
                        campaign_id=campaign_id,
                        status="COMPLETED",
                        name=campaign.name,
                        total=campaign.total_contacts,
                        sent=campaign.sent_count,
                        delivered=campaign.delivered_count,
                        failed=campaign.failed_count,
                        duration_seconds=duration,
                        completed_at=now.isoformat(),
                    )
                )

                # Clear batch stats
                if str(campaign_id) in self.batch_stats:
                    del self.batch_stats[str(campaign_id)]

    async def pause_campaign(self, campaign_id: UUID):
        """Pause campaign with notification"""
        async with self.uow:
            campaign = await self.uow.campaigns.get_by_id(campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")

            campaign.status = CampaignStatus.PAUSED
            campaign.updated_at = get_utc_now()
            self.uow.session.add(campaign)
            await self.uow.commit()

            await self._notify_event(
                CampaignStatusEvent(
                    campaign_id=campaign_id,
                    status="PAUSED",
                    name=campaign.name,
                )
            )

    async def resume_campaign(self, campaign_id: UUID):
        """Resume campaign with notification"""
        async with self.uow:
            campaign = await self.uow.campaigns.get_by_id(campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")

            campaign.status = CampaignStatus.RUNNING
            campaign.updated_at = get_utc_now()
            self.uow.session.add(campaign)
            await self.uow.commit()

            await self._notify_event(
                CampaignStatusEvent(
                    campaign_id=campaign_id,
                    status="RUNNING",
                    name=campaign.name,
                )
            )

    async def notify_batch_progress(
        self,
        campaign_id: UUID,
        batch_number: int,
        batch_size: int,
        processed: int,
        successful: int,
        failed: int,
    ):
        """Notify batch processing progress"""
        await self._notify_event(
            BatchProgressEvent(
                campaign_id=campaign_id,
                batch_number=batch_number,
                batch_size=batch_size,
                processed=processed,
                successful=successful,
                failed=failed,
            )
        )
