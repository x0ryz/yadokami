from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models import (
    Campaign,
    CampaignDeliveryStatus,
    CampaignStatus,
    Contact,
    get_utc_now,
)
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.contact import ContactRepository
from src.repositories.template import TemplateRepository
from src.services.campaign.tracker import CampaignProgressTracker
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
        trackers: dict[str, CampaignProgressTracker],
    ):
        self.session = session
        self.campaigns = campaigns_repo
        self.campaign_contacts = campaign_contacts_repo
        self.contacts = contacts_repo
        self.template_repo = template_repo
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
            campaign
        )

        # Prepare template parameters based on variable_mapping
        template_params = None
        logger.info(
            f"Campaign {campaign_id} variable_mapping: {campaign.variable_mapping} "
            f"(type: {type(campaign.variable_mapping)}, len: {len(campaign.variable_mapping) if campaign.variable_mapping else 0})"
        )

        try:
            if (
                campaign.message_type == "template"
                and campaign.variable_mapping
                and len(campaign.variable_mapping) > 0
            ):
                contact_data = {
                    "name": contact.name,
                    "phone_number": contact.phone_number,
                    "custom_data": contact.custom_data or {},
                }
                params = render_template_params(
                    campaign.variable_mapping,
                    contact_data,
                )
                logger.info(f"Rendered template params: {params}")
                # Only set template_params if we have actual parameters
                if params:
                    template_params = params

            logger.info(f"Final template_params being sent: {template_params}")
        except ValueError as validation_error:
            # Handle missing contact data - create failed message
            logger.warning(
                f"Contact {contact_id} validation failed: {validation_error}")

            # Create a failed message to store the error
            from src.models import Message, MessageDirection, MessageStatus
            message = Message(
                waba_phone_id=campaign.waba_phone_id,
                contact_id=contact.id,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.FAILED,
                message_type=campaign.message_type,
                body=template_name if campaign.message_type == "template" else body_text,
                template_id=campaign.template_id,
                error_code=None,
                error_message=str(validation_error)[:500],
            )
            self.session.add(message)
            await self.session.flush()
            await self.session.refresh(message)

            # Update campaign contact with the failed message
            contact_link.message_id = message.id
            contact_link.status = CampaignDeliveryStatus.FAILED
            contact_link.retry_count += 1
            self.session.add(contact_link)

            # Increment failed_count only on first failure (retry_count was 0)
            if contact_link.retry_count == 1:
                campaign.failed_count += 1
            self.session.add(campaign)

            await self.session.commit()

            # Update tracker
            tracker = self.trackers.get(str(campaign_id))
            if tracker:
                tracker.increment_failed()
            
            # Notify about validation failure via WebSocket
            await self.notifier.notify_message_status(
                message_id=message.id,
                wamid="",
                status="failed",
                campaign_id=str(campaign_id),
                contact_id=str(contact_id),
                phone=contact.phone_number,
                contact_name=contact.name,
                error=str(validation_error)[:500],
                retry_count=contact_link.retry_count,
            )

            return False

        try:
            message = await self.sender.send_to_contact(
                contact=contact,
                message_type=campaign.message_type,
                body=body_text,
                template_id=campaign.template_id,
                template_name=template_name,
                template_language_code=template_language_code,
                template_parameters=template_params,
                is_campaign=True,
                phone_id=str(campaign.waba_phone_id)
                if campaign.waba_phone_id
                else None,
            )

            # Check if the message actually failed (for campaign messages, 
            # send_to_contact returns failed message instead of raising)
            from src.models import MessageStatus
            if message.status == MessageStatus.FAILED:
                logger.warning(
                    f"Message {message.id} for contact {contact_id} failed: {message.error_message}"
                )
                
                # Update campaign contact status to FAILED
                contact_link.message_id = message.id
                contact_link.status = CampaignDeliveryStatus.FAILED
                contact_link.retry_count += 1
                self.session.add(contact_link)

                # Increment failed_count only on first failure
                if contact_link.retry_count == 1:
                    campaign.failed_count += 1
                self.session.add(campaign)

                await self.session.commit()
                
                # Update tracker
                tracker = self.trackers.get(str(campaign_id))
                if tracker:
                    tracker.increment_failed()
                
                # Notify about failed message via WebSocket
                await self.notifier.notify_message_status(
                    message_id=message.id,
                    wamid=message.wamid or "",
                    status="failed",
                    campaign_id=str(campaign_id),
                    contact_id=str(contact_id),
                    phone=contact.phone_number,
                    contact_name=contact.name,
                    error=message.error_message,
                    error_code=message.error_code,
                    retry_count=contact_link.retry_count,
                )
                
                return False

            # Message sent successfully
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
            logger.warning(f"Failed to send message to {contact_id}: {e}")

            # Rollback any uncommitted changes from the failed send
            await self.session.rollback()

            # Check if we got a failed message from send_to_contact
            # (it returns failed message for campaigns instead of raising)
            # If so, we need to refetch it in a new transaction
            from src.models import Message, MessageDirection, MessageStatus
            from src.repositories.message import MessageRepository
            
            msg_repo = MessageRepository(self.session)
            failed_message = None
            
            # Try to get the last message for this contact that's in FAILED state
            if contact.last_message_id:
                last_msg = await msg_repo.get_by_id(contact.last_message_id)
                if last_msg and last_msg.status == MessageStatus.FAILED:
                    failed_message = last_msg
                    logger.info(f"Found existing failed message {failed_message.id} for contact {contact_id}")
            
            # If we didn't find an existing failed message, create one
            if not failed_message:
                logger.info(f"Creating new failed message for contact {contact_id}")
                failed_message = Message(
                    waba_phone_id=campaign.waba_phone_id,
                    contact_id=contact.id,
                    direction=MessageDirection.OUTBOUND,
                    status=MessageStatus.FAILED,
                    message_type=campaign.message_type,
                    body=template_name if campaign.message_type == "template" else body_text,
                    template_id=campaign.template_id,
                    error_code=None,
                    error_message=str(e)[:500],
                )
                self.session.add(failed_message)
            
            try:
                if not failed_message.id:
                    await self.session.flush()
                    await self.session.refresh(failed_message)

                # Link the failed message to campaign contact
                contact_link.message_id = failed_message.id
                contact_link.status = CampaignDeliveryStatus.FAILED
                contact_link.retry_count += 1
                self.session.add(contact_link)

                # Increment failed_count only on first failure (retry_count was 0)
                if contact_link.retry_count == 1:
                    campaign.failed_count += 1
                self.session.add(campaign)

                await self.session.commit()
                
                # Update tracker
                tracker = self.trackers.get(str(campaign_id))
                if tracker:
                    tracker.increment_failed()

                logger.info(
                    f"Recorded failed message {failed_message.id} for contact {contact_id}"
                )
            except Exception as commit_error:
                logger.error(
                    f"Failed to commit failure state: {commit_error}")
                await self.session.rollback()

            return False

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
        contact_link.retry_count += 1
        contact_link.updated_at = now
        self.session.add(contact_link)

        # Increment failed_count only on first failure (retry_count was 0)
        if contact_link.retry_count == 1:
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

    def _can_send_message(self, campaign: Campaign, contact_link) -> bool:
        """Check if message can be sent to contact."""
        if campaign.status != CampaignStatus.RUNNING:
            logger.debug(
                f"Campaign {campaign.id} not running: status={campaign.status}, "
                f"updated_at={campaign.updated_at}"
            )
            return False

        # Only allow sending to QUEUED contacts (first attempt)
        # Note: Retry logic removed since failed contacts aren't republished to queue
        if contact_link.status == CampaignDeliveryStatus.QUEUED:
            return True

        logger.debug(
            f"Contact link {contact_link.id} already processed "
            f"with status {contact_link.status}"
        )
        return False

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
        from src.models import ContactStatus

        # Update contact link
        contact_link.status = CampaignDeliveryStatus.SENT
        contact_link.message_id = message_id
        contact_link.updated_at = now
        self.session.add(contact_link)

        # Update contact
        contact.last_message_at = now
        contact.updated_at = now
        # Після розсилки ставимо контакт в архів
        contact.status = ContactStatus.ARCHIVED
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
