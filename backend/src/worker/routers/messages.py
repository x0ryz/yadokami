from faststream import Depends
from faststream.nats import NatsRouter

from src.schemas import WhatsAppMessage
from src.services.messaging.sender import MessageSenderService
from src.worker.dependencies import get_message_sender_service, limiter, logger

router = NatsRouter()


@router.subscriber("messages.manual_send")
async def handle_messages_task(
    message: WhatsAppMessage,
    sender_service: MessageSenderService = Depends(get_message_sender_service),
):
    async with limiter:
        with logger.contextualize(request_id=message.request_id):
            await sender_service.send_manual_message(message)


@router.subscriber("messages.schedule")
async def handle_scheduled_message(
    data: dict,
    sender_service: MessageSenderService = Depends(get_message_sender_service),
):
    """
    Handle scheduled message creation.
    Creates a message in DB with PENDING status and scheduled_at timestamp.
    """
    from datetime import datetime
    from uuid import UUID
    
    async with limiter:
        request_id = data.get("request_id", "unknown")
        with logger.contextualize(request_id=request_id):
            await sender_service.create_scheduled_message(
                phone_number=data["phone_number"],
                message_type=data["type"],
                body=data["body"],
                scheduled_at=datetime.fromisoformat(data["scheduled_at"]),
                reply_to_message_id=UUID(data["reply_to_message_id"]) if data.get("reply_to_message_id") else None,
                phone_id=data.get("phone_id"),
            )


@router.subscriber("messages.send_scheduled_now")
async def handle_send_scheduled_now(
    data: dict,
    sender_service: MessageSenderService = Depends(get_message_sender_service),
):
    """Send a scheduled message immediately."""
    from uuid import UUID
    from src.repositories.message import MessageRepository
    from src.core.database import async_session_maker
    
    message_id = UUID(data["message_id"])
    
    async with async_session_maker() as session:
        message_repo = MessageRepository(session)
        message = await message_repo.get_by_id(message_id)
        
        if not message or not message.scheduled_at:
            logger.warning(f"Message {message_id} not found or not scheduled")
            return
        
        from src.models.base import get_utc_now
        
        # Set scheduled_at to now to trigger immediate sending by scheduler
        message.scheduled_at = get_utc_now()
        session.add(message)
        await session.commit()
        
        logger.info(f"Scheduled message {message_id} will be sent immediately by scheduler")


        time.sleep(10) # Placeholder
         
@router.subscriber("messages.delete_scheduled")
async def handle_delete_scheduled(
    data: dict,
):
    """Delete a scheduled message."""
    from uuid import UUID
    from src.repositories.message import MessageRepository
    from src.core.database import async_session_maker
    
    message_id = UUID(data["message_id"])
    
    async with async_session_maker() as session:
        message_repo = MessageRepository(session)
        message = await message_repo.get_by_id(message_id)
        
        if not message:
            logger.warning(f"Message {message_id} not found")
            return
        
        await message_repo.delete(message_id)
        await session.commit()
        
        logger.info(f"Deleted scheduled message {message_id}")


@router.subscriber("messages.send_scheduled_item")
async def handle_send_scheduled_item(
    data: dict,
    sender_service: MessageSenderService = Depends(get_message_sender_service),
):
    """
    Handle checking and sending a single scheduled message.
    Triggered by scheduled_messages_checker task.
    """
    from uuid import UUID
    from src.models import MessageStatus
    from src.repositories.message import MessageRepository
    from src.repositories.contact import ContactRepository
    
    message_id = UUID(data["message_id"])
    logger.debug(f"Processing scheduled message item: {message_id}")
    
    # We need to access repositories via the session injected into sender_service
    # MessageSenderService has .session, .messages, .contacts attributes
    
    # 1. Fetch message and verify it's still pending
    message = await sender_service.messages.get_by_id(message_id)
    
    if not message:
        logger.warning(f"Message {message_id} not found during processing")
        return
        
    if message.status != MessageStatus.PENDING:
        logger.info(f"Message {message_id} is no longer PENDING (status: {message.status}), skipping")
        return
        
    # 2. Get contact
    contact = await sender_service.contacts.get_by_id(message.contact_id)
    if not contact:
        logger.error(f"Contact not found for message {message.id}")
        message.status = MessageStatus.FAILED
        message.error_message = "Contact not found"
        sender_service.session.add(message)
        await sender_service.session.commit()
        return

    try:
        # 3. Prepare details
        template_name = None
        template_language_code = None
        template_id = message.template_id
        
        if message.message_type == "template" and template_id:
            from src.repositories.template import TemplateRepository
            template_repo = TemplateRepository(sender_service.session)
            template = await template_repo.get_by_id(template_id)
            if template:
                template_name = template.name
                template_language_code = template.language
        
        # 4. Send using sender service (reusing existing message entity)
        await sender_service.send_to_contact(
            contact=contact,
            message_type=message.message_type,
            body=message.body or "",
            template_id=template_id,
            template_name=template_name,
            template_language_code=template_language_code,
            is_campaign=False,
            reply_to_message_id=message.reply_to_message_id,
            existing_message=message,
        )
        
        # Determine if we should commit here. 
        # send_to_contact does NOT commit, so we typically must commit.
        # But `MessageSenderService.send_manual_message` commits.
        # Let's commit to be safe and ensure status update persists.
        await sender_service.session.commit()
        logger.info(f"Successfully processed scheduled message {message.id}")
        
    except Exception as e:
        logger.error(f"Failed to send scheduled message {message.id}: {e}")
        await sender_service.session.rollback()
        
        # Mark message as failed in a separate transaction if possible, 
        # or stick to the current session if rollback happened cleanly.
        try:
            # Re-fetch or re-attach if needed, but simple attribute set might work 
            # if session is still valid. Simplest is to just use the session again.
            message.status = MessageStatus.FAILED
            message.error_message = str(e)[:500]
            sender_service.session.add(message)
            await sender_service.session.commit()
        except Exception as update_error:
            logger.error(f"Failed to update message status after error: {update_error}")

