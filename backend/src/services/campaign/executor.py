from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    Campaign,
    CampaignDeliveryStatus,
    CampaignStatus,
    Contact,
    get_utc_now,
)
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
from src.services.campaign.tracker import CampaignProgressTracker
from src.services.messaging.sender import MessageSenderService
from src.services.notifications.service import NotificationService


class CampaignMessageExecutor:
    """Handles individual message sending within campaigns."""

    def __init__(
        self,
        session: AsyncSession,
        campaigns_repo: CampaignRepository,
        campaign_contacts_repo: CampaignContactRepository,
        contacts_repo: ContactRepository,
        message_sender: MessageSenderService,
        notifier: NotificationService,
        trackers: dict[str, CampaignProgressTracker],
    ):
        self.session = session
        self.campaigns = campaigns_repo
        self.campaign_contacts = campaign_contacts_repo
        self.contacts = contacts_repo
        self.sender = message_sender
        self.notifier = notifier
        self.trackers = trackers

    async def send_message(
        self, campaign_id: UUID, link_id: UUID, contact_id: UUID
    ) -> bool:
        """
        Attempt to send a message to a contact.
        Returns True if successful, False otherwise.
        """
        campaign = await self.campaigns.get_by_id_with_template(campaign_id)
        contact_link = await self.campaign_contacts.get_by_id(link_id)
        contact = await self.contacts.get_by_id(contact_id)

        if not all([campaign, contact_link, contact]):
            logger.warning(
                f"Missing entities for campaign {campaign_id}, "
                f"link {link_id}, contact {contact_id}"
            )
            return False

        if not self._can_send_message(campaign, contact_link):
            return False

        template_name, body_text, template_language_code = self._prepare_message_data(
            campaign)

        try:
            message = await self.sender.send_to_contact(
                contact=contact,
                message_type=campaign.message_type,
                body=body_text,
                template_id=campaign.template_id,
                template_name=template_name,
                template_language_code=template_language_code,
                is_campaign=True,
                phone_id=str(campaign.waba_phone_id)
                if campaign.waba_phone_id
                else None,
            )

            now = get_utc_now()
            self._update_after_send(
                contact_link, contact, campaign, message.id, now)

            # Commit changes to database
            await self.session.commit()

            # Refresh campaign object to get updated counts
            await self.session.refresh(campaign)

            # Update tracker
            tracker = self.trackers.get(str(campaign_id))
            if tracker:
                tracker.increment_sent()

            # Notify
            await self.notifier.notify_message_status(
                message_id=message.id,
                wamid=message.wamid,
                status="sent",
                campaign_id=str(campaign_id),
                contact_id=str(contact_id),
                phone=contact.phone_number,
                contact_name=contact.name,
            )

            # Notify progress
            await self._notify_progress(campaign)

            return True

        except Exception as e:
            logger.exception(f"Failed to send message to {contact_id}")
            raise

    async def handle_send_failure(
        self, campaign_id: UUID, link_id: UUID, error_msg: str
    ):
        """Handle message send failure."""
        contact_link = await self.campaign_contacts.get_by_id(link_id)
        campaign = await self.campaigns.get_by_id(campaign_id)

        if not contact_link or not campaign:
            return

        now = get_utc_now()
        contact_link.status = CampaignDeliveryStatus.FAILED
        contact_link.error_message = error_msg[:500]
        contact_link.retry_count += 1
        contact_link.updated_at = now
        self.session.add(contact_link)

        campaign.failed_count += 1
        campaign.updated_at = now
        self.session.add(campaign)

        await self.session.commit()
        await self.session.refresh(campaign)

        # Update tracker
        tracker = self.trackers.get(str(campaign_id))
        if tracker:
            tracker.increment_failed()

        # Notify
        await self.notifier.notify_message_status(
            message_id=contact_link.message_id or contact_link.id,
            wamid="",
            status="failed",
            campaign_id=str(campaign_id),
            contact_id=str(contact_link.contact_id),
            error=error_msg,
            retry_count=contact_link.retry_count,
        )

    # ==================== Private Methods ====================

    @staticmethod
    def _can_send_message(campaign: Campaign, contact_link) -> bool:
        """Check if message can be sent to contact."""
        if campaign.status != CampaignStatus.RUNNING:
            logger.debug(f"Campaign {campaign.id} not running")
            return False

        # Skip if contact already processed
        if contact_link.status != CampaignDeliveryStatus.QUEUED:
            logger.debug(
                f"Contact link {contact_link.id} already processed "
                f"with status {contact_link.status}"
            )
            return False

        return True

    @staticmethod
    def _prepare_message_data(campaign: Campaign) -> tuple[str | None, str, str | None]:
        """Prepare message data for sending."""
        template_name = None
        template_language_code = None
        body_text = campaign.message_body

        if campaign.message_type == "template" and campaign.template:
            template_name = campaign.template.name
            template_language_code = campaign.template.language
            body_text = template_name

        return template_name, body_text, template_language_code

    def _update_after_send(
        self, contact_link, contact: Contact, campaign: Campaign, message_id, now
    ):
        """Update entities after successful message send."""
        # Update contact link
        contact_link.status = CampaignDeliveryStatus.SENT
        contact_link.message_id = message_id
        contact_link.updated_at = now
        self.session.add(contact_link)

        # Update contact
        contact.last_message_at = now
        contact.updated_at = now
        self.session.add(contact)

        # Update campaign stats
        campaign.sent_count += 1
        campaign.updated_at = now
        self.session.add(campaign)

    async def _notify_progress(self, campaign: Campaign):
        """Send campaign progress notification."""
        tracker = self.trackers.get(str(campaign.id))
        if not tracker:
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

    @staticmethod
    def _calculate_progress(campaign: Campaign) -> float:
        """Calculate campaign progress percentage."""
        if campaign.total_contacts == 0:
            return 0.0
        return (campaign.sent_count / campaign.total_contacts) * 100

    @staticmethod
    def _calculate_remaining(campaign: Campaign) -> int:
        """Calculate remaining contacts to process."""
        return campaign.total_contacts - campaign.sent_count - campaign.failed_count
