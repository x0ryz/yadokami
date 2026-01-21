from uuid import UUID

from faststream import Depends
from faststream.nats import NatsMessage, NatsRouter

from src.core.broker import broker
from src.core.database import async_session_maker
from src.repositories.campaign import CampaignContactRepository
from src.services.campaign.sender import CampaignSenderService
from src.worker.dependencies import (
    get_campaign_sender_service,
    limiter,
    logger,
)

router = NatsRouter()


@router.subscriber("campaigns.send", stream="campaigns", durable="campaign-sender")
async def handle_campaign_send(
    campaign_id: str,
    link_id: str,
    contact_id: str,
    msg: NatsMessage,
    service: CampaignSenderService = Depends(get_campaign_sender_service),
):
    async with limiter:
        dedup_key = f"{campaign_id}_{contact_id}"
        kv = None
        try:
            js = broker._connection.jetstream()
            kv = await js.key_value("processed_messages")
            if await kv.get(dedup_key):
                logger.info(f"Skipping duplicate: {dedup_key}")
                return
        except Exception:
            pass

        with logger.contextualize(campaign_id=campaign_id, contact_id=contact_id):
            try:
                await service.send_single_message(
                    campaign_id=UUID(campaign_id),
                    link_id=UUID(link_id),
                    contact_id=UUID(contact_id),
                )
                await broker.publish(
                    {"type": "campaign_sent", "id": contact_id},
                    subject="notify.frontend",
                )
                if kv:
                    await kv.put(dedup_key, b"sent")
            except Exception as e:
                logger.exception(f"Failed to send: {e}")
                raise e


@router.subscriber("campaigns.start", stream="campaigns", durable="campaign-starter")
async def handle_campaign_start(
    campaign_id: str,
    service: CampaignSenderService = Depends(get_campaign_sender_service),
):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            logger.info(f"Starting campaign {campaign_id}")
            await service.start_campaign(UUID(campaign_id))

            batch_size = 100
            offset = 0
            while True:
                async with async_session_maker() as session:
                    repo = CampaignContactRepository(session)
                    contacts = await repo.get_sendable_contacts(
                        UUID(campaign_id), limit=batch_size, offset=offset
                    )

                if not contacts:
                    break

                for link in contacts:
                    await broker.publish(
                        {
                            "campaign_id": campaign_id,
                            "link_id": str(link.id),
                            "contact_id": str(link.contact_id),
                        },
                        subject="campaigns.send",
                        stream="campaigns",
                    )
                offset += len(contacts)

            logger.info(f"Campaign started. Tasks published: {offset}")
        except Exception as e:
            logger.exception(f"Start failed: {e}")


@router.subscriber("campaigns.resume", stream="campaigns", durable="campaign-resumer")
async def handle_campaign_resume(
    campaign_id: str,
    service: CampaignSenderService = Depends(get_campaign_sender_service),
):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            logger.info(f"Resuming campaign {campaign_id}")
            await service.resume_campaign(UUID(campaign_id))

            batch_size = 100
            offset = 0
            while True:
                # Get remaining QUEUED contacts
                async with async_session_maker() as session:
                    repo = CampaignContactRepository(session)
                    contacts = await repo.get_sendable_contacts(
                        UUID(campaign_id), limit=batch_size, offset=offset
                    )

                if not contacts:
                    break

                for link in contacts:
                    await broker.publish(
                        {
                            "campaign_id": campaign_id,
                            "link_id": str(link.id),
                            "contact_id": str(link.contact_id),
                        },
                        subject="campaigns.send",
                        stream="campaigns",
                    )
                offset += len(contacts)

            logger.info(f"Campaign resumed. Tasks published: {offset}")
        except Exception as e:
            logger.exception(f"Resume failed: {e}")


@router.subscriber("campaigns.pause", stream="campaigns", durable="campaign-pauser")
async def handle_campaign_pause(
    campaign_id: str,
    service: CampaignSenderService = Depends(get_campaign_sender_service),
):
    with logger.contextualize(campaign_id=campaign_id):
        try:
            logger.info(f"Pausing campaign {campaign_id}")
            await service.pause_campaign(UUID(campaign_id))
        except Exception as e:
            logger.exception(f"Pause failed: {e}")
