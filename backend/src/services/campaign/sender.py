from uuid import UUID

from loguru import logger

from src.core.uow import UnitOfWork
from src.models import (
    Campaign,
    CampaignDeliveryStatus,
    CampaignStatus,
    get_utc_now,
)
from src.services.campaign.tracker import CampaignProgressTracker
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService


class CampaignSenderService:
    """
    Service for managing campaign message sending.

    Responsibilities:
    - Start/pause/resume campaigns
    - Send individual messages to contacts
    - Track campaign progress
    - Notify about campaign events
    """

    def __init__(
        self,
        uow: UnitOfWork,
        message_sender: MessageSenderService,
        notifier: NotificationService,
    ):
        self.uow = uow
        self.sender = message_sender
        self.notifier = notifier
        self.trackers: dict[str, CampaignProgressTracker] = {}

    async def start_campaign(self, campaign_id: UUID):
        """
        Start a campaign.

        Args:
            campaign_id: UUID of campaign to start

        Raises:
            ValueError: If campaign not found, in wrong status, or has no contacts
        """
        async with self.uow:
            campaign = await self._get_campaign_or_raise(campaign_id)
            self._validate_can_start(campaign)

            now = get_utc_now()

            # Update campaign status
            campaign.status = CampaignStatus.RUNNING
            campaign.started_at = now
            campaign.updated_at = now
            self.uow.session.add(campaign)

            # Initialize progress tracker
            self.trackers[str(campaign_id)] = CampaignProgressTracker(
                campaign_id=campaign_id
            )

            logger.info(f"Campaign {campaign_id} started")

            # Notify and commit
            await self.notifier.notify_campaign_status(
                campaign_id=campaign_id,
                status="RUNNING",
                name=campaign.name,
                total_contacts=campaign.total_contacts,
                message_type=campaign.message_type,
                started_at=now.isoformat(),
            )

            await self._notify_progress(campaign)
            await self.uow.commit()

    async def send_single_message(
        self, campaign_id: UUID, link_id: UUID, contact_id: UUID
    ):
        """
        Send a single message to a contact as part of a campaign.

        Args:
            campaign_id: UUID of the campaign
            link_id: UUID of the campaign-contact link
            contact_id: UUID of the contact
        """
        try:
            await self._attempt_send_message(campaign_id, link_id, contact_id)
        except Exception as e:
            logger.exception(f"Failed to send campaign message to {contact_id}")
            await self._handle_send_failure(campaign_id, link_id, str(e))
        finally:
            await self._check_campaign_completion(campaign_id)

    async def pause_campaign(self, campaign_id: UUID):
        """Pause a running campaign."""
        async with self.uow:
            campaign = await self._get_campaign_or_raise(campaign_id)

            campaign.status = CampaignStatus.PAUSED
            campaign.updated_at = get_utc_now()
            self.uow.session.add(campaign)
            await self.uow.commit()

            logger.info(f"Campaign {campaign_id} paused")

            await self.notifier.notify_campaign_status(
                campaign_id=campaign_id,
                status="PAUSED",
                name=campaign.name,
            )

    async def resume_campaign(self, campaign_id: UUID):
        """Resume a paused campaign."""
        async with self.uow:
            campaign = await self._get_campaign_or_raise(campaign_id)

            campaign.status = CampaignStatus.RUNNING
            campaign.updated_at = get_utc_now()
            self.uow.session.add(campaign)
            await self.uow.commit()

            logger.info(f"Campaign {campaign_id} resumed")

            await self.notifier.notify_campaign_status(
                campaign_id=campaign_id,
                status="RUNNING",
                name=campaign.name,
            )

    async def notify_batch_progress(
        self, campaign_id: UUID, batch_number: int, stats: dict
    ):
        """Notify about batch processing progress."""
        await self.notifier.notify_batch_progress(
            campaign_id=campaign_id, batch_number=batch_number, stats=stats
        )

    # ==================== Private Methods ====================

    async def _attempt_send_message(
        self, campaign_id: UUID, link_id: UUID, contact_id: UUID
    ):
        """
        Attempt to send a message.

        Transaction scope: This entire method is ONE transaction.
        """
        async with self.uow:
            campaign = await self.uow.campaigns.get_by_id_with_template(campaign_id)
            contact_link = await self.uow.campaign_contacts.get_by_id(link_id)
            contact = await self.uow.contacts.get_by_id(contact_id)

            if not all([campaign, contact_link, contact]):
                logger.warning(
                    f"Missing entities for campaign {campaign_id}, "
                    f"link {link_id}, contact {contact_id}"
                )
                return

            if not self._can_send_message(campaign, contact_link):
                return

            template_name, body_text = self._prepare_message_data(campaign)

            message = await self.sender.send_to_contact(
                contact=contact,
                message_type=campaign.message_type,
                body=body_text,
                template_id=campaign.template_id,
                template_name=template_name,
                is_campaign=True,
                phone_id=str(campaign.waba_phone_id)
                if campaign.waba_phone_id
                else None,
            )

            now = get_utc_now()
            self._update_after_send(contact_link, contact, campaign, message.id, now)

        tracker = self.trackers.get(str(campaign_id))
        if tracker:
            tracker.increment_sent()

        # 6. Notify (outside transaction)
        await self.notifier.notify_message_status(
            message_id=message.id,
            wamid=message.wamid,
            status="sent",
            campaign_id=str(campaign_id),
            contact_id=str(contact_id),
            phone=contact.phone_number,
            contact_name=contact.name,
        )

        # Re-open transaction for progress notification
        async with self.uow:
            campaign = await self.uow.campaigns.get_by_id(campaign_id)
            if campaign:
                await self._notify_progress(campaign)

    async def _handle_send_failure(
        self, campaign_id: UUID, link_id: UUID, error_msg: str
    ):
        """
        Handle send failure.

        Transaction scope: Separate transaction for failure handling.
        """
        async with self.uow:
            contact_link = await self.uow.campaign_contacts.get_by_id(link_id)
            campaign = await self.uow.campaigns.get_by_id(campaign_id)

            if not contact_link or not campaign:
                return

            now = get_utc_now()
            contact_link.status = CampaignDeliveryStatus.FAILED
            contact_link.error_message = error_msg[:500]
            contact_link.retry_count += 1
            contact_link.updated_at = now
            self.uow.session.add(contact_link)

            campaign.failed_count += 1
            campaign.updated_at = now
            self.uow.session.add(campaign)

        # Update tracker (outside transaction)
        tracker = self.trackers.get(str(campaign_id))
        if tracker:
            tracker.increment_failed()

        # Notify (outside transaction)
        await self.notifier.notify_message_status(
            message_id=contact_link.message_id or contact_link.id,
            wamid="",
            status="failed",
            campaign_id=str(campaign_id),
            contact_id=str(contact_link.contact_id),
            error=error_msg,
            retry_count=contact_link.retry_count,
        )

    async def _mark_as_failed(self, link, campaign, error_msg: str):
        """Mark a contact link as failed."""
        now = get_utc_now()

        # Update link
        link.status = CampaignDeliveryStatus.FAILED
        link.error_message = error_msg[:500]
        link.retry_count += 1
        link.updated_at = now
        self.uow.session.add(link)

        # Update campaign stats
        campaign.failed_count += 1
        campaign.updated_at = now
        self.uow.session.add(campaign)

        await self.uow.commit()

        # Notify
        await self.notifier.notify_message_status(
            message_id=link.message_id or link.id,
            wamid="",
            status="failed",
            campaign_id=str(campaign.id),
            contact_id=str(link.contact_id),
            error=error_msg,
            retry_count=link.retry_count,
        )

    async def _notify_progress(self, campaign: Campaign):
        """Send campaign progress notification."""
        tracker = self.trackers.get(str(campaign.id))
        if not tracker:
            logger.warning(f"No tracker found for campaign {campaign.id}")
            return

        # Calculate metrics
        progress_percent = self._calculate_progress(campaign)
        remaining = self._calculate_remaining(campaign)

        # Use tracker for rate and ETA calculations
        current_rate = tracker.calculate_rate()
        estimated_completion = tracker.estimate_completion(remaining)

        await self.notifier.notify_campaign_progress(
            campaign_id=campaign.id,
            stats={
                "total": campaign.total_contacts,
                "sent": campaign.sent_count,
                "delivered": campaign.delivered_count,
                "failed": campaign.failed_count,
                "pending": remaining,
                "progress_percent": round(progress_percent, 2),
                "estimated_completion": estimated_completion,
                "current_rate": round(current_rate, 2),
            },
        )

    async def _check_campaign_completion(self, campaign_id: UUID):
        """Check if campaign is completed and update status."""
        async with self.uow:
            campaign = await self.uow.campaigns.get_by_id(campaign_id)

            if not campaign or campaign.status != CampaignStatus.RUNNING:
                return

            # Check if there are remaining contacts
            remaining = await self.uow.campaign_contacts.get_sendable_contacts(
                campaign_id, limit=1
            )

            if remaining:
                return  # Still have contacts to process

            # Campaign completed
            await self._complete_campaign(campaign)

    async def _complete_campaign(self, campaign: Campaign):
        """Mark campaign as completed and notify."""
        now = get_utc_now()

        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = now
        campaign.updated_at = now
        self.uow.session.add(campaign)
        await self.uow.commit()

        # Get tracker for duration
        tracker = self.trackers.get(str(campaign.id))
        duration = tracker.get_elapsed_time() if tracker else None

        logger.info(f"Campaign {campaign.id} completed")

        # Notify
        await self.notifier.notify_campaign_status(
            campaign_id=campaign.id,
            status="COMPLETED",
            name=campaign.name,
            total=campaign.total_contacts,
            sent=campaign.sent_count,
            delivered=campaign.delivered_count,
            failed=campaign.failed_count,
            duration_seconds=duration,
            completed_at=now.isoformat(),
        )

        # Clean up tracker
        if str(campaign.id) in self.trackers:
            del self.trackers[str(campaign.id)]

    # ==================== Helper Methods ====================

    async def _get_campaign_or_raise(self, campaign_id: UUID) -> Campaign:
        """Get campaign by ID or raise ValueError."""
        campaign = await self.uow.campaigns.get_by_id_with_template(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        return campaign

    def _validate_can_start(self, campaign: Campaign):
        """Validate that campaign can be started."""
        if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
            raise ValueError(f"Cannot start campaign in {campaign.status} status")

        if campaign.total_contacts == 0:
            raise ValueError("Cannot start campaign with no contacts")

    def _can_send_message(self, campaign: Campaign, contact_link) -> bool:
        """Check if message can be sent to contact."""
        if campaign.status != CampaignStatus.RUNNING:
            logger.debug(f"Campaign {campaign.id} not running")
            return False

        if contact_link.status == CampaignDeliveryStatus.SENT:
            logger.debug(f"Contact link {contact_link.id} already sent")
            return False

        return True

    def _prepare_message_data(self, campaign: Campaign) -> tuple[str | None, str]:
        """
        Prepare message data for sending.

        Returns:
            tuple: (template_name, body_text)
        """
        template_name = None
        body_text = campaign.message_body

        if campaign.message_type == "template" and campaign.template:
            template_name = campaign.template.name
            body_text = template_name

        return template_name, body_text

    def _update_after_send(self, contact_link, contact, campaign, message_id, now):
        """Update entities after successful message send."""
        # Update contact link
        contact_link.status = CampaignDeliveryStatus.SENT
        contact_link.message_id = message_id
        contact_link.updated_at = now
        self.uow.session.add(contact_link)

        # Update contact
        contact.last_message_at = now
        contact.updated_at = now
        self.uow.session.add(contact)

        # Update campaign stats
        campaign.sent_count += 1
        campaign.updated_at = now
        self.uow.session.add(campaign)

    def _calculate_progress(self, campaign: Campaign) -> float:
        """Calculate campaign progress percentage."""
        if campaign.total_contacts == 0:
            return 0.0
        return (campaign.sent_count / campaign.total_contacts) * 100

    def _calculate_remaining(self, campaign: Campaign) -> int:
        """Calculate remaining contacts to process."""
        return campaign.total_contacts - campaign.sent_count - campaign.failed_count
