from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.broker import broker
from src.core.dependencies import get_contact_import_service, get_session
from src.core.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError
from src.models import CampaignStatus, get_utc_now
from src.repositories.campaign import CampaignContactRepository, CampaignRepository
from src.repositories.template import TemplateRepository
from src.schemas import (
    CampaignContactResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignSchedule,
    CampaignUpdate,
    ContactImport,
    ContactImportResult,
)
from src.services.campaign.importer import ContactImportService

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new campaign."""
    campaign_repo = CampaignRepository(session)
    template_repo = TemplateRepository(session)

    if data.message_type == "template" and not data.template_id:
        raise BadRequestError(
            detail="template_id is required when message_type is 'template'"
        )

    if data.message_type == "text" and not data.message_body:
        raise BadRequestError(
            detail="message_body is required when message_type is 'text'",
        )

    if data.template_id:
        template = await template_repo.get_by_id(data.template_id)
        if not template:
            raise NotFoundError(
                detail=f"Template with id {data.template_id} not found",
            )
        if template.status != "APPROVED":
            raise BadRequestError(
                detail="Template must be APPROVED",
            )

    campaign = await campaign_repo.create(
        name=data.name,
        message_type=data.message_type,
        template_id=data.template_id,
        waba_phone_id=data.waba_phone_id,
        message_body=data.message_body,
        status=CampaignStatus.DRAFT,
    )

    await session.commit()

    logger.info(f"Campaign created: {campaign.id} - {campaign.name}")
    return campaign


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    status: CampaignStatus | None = None,
    session: AsyncSession = Depends(get_session),
):
    """
    List campaigns.
    Progress percent will be automatically calculated for each item.
    """
    campaigns = await CampaignRepository(session).list_with_status(status=status)
    return campaigns


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    campaign = await CampaignRepository(session).get_by_id(campaign_id)
    if not campaign:
        raise NotFoundError(detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    session: AsyncSession = Depends(get_session),
):
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get_by_id(campaign_id)

    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status != CampaignStatus.DRAFT:
        raise BadRequestError(
            detail="Can only update campaigns in DRAFT status",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)

    campaign.updated_at = get_utc_now()
    session.add(campaign)

    await session.commit()

    logger.info(f"Campaign updated: {campaign_id}")
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get_by_id(campaign_id)

    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.COMPLETED]:
        raise BadRequestError(
            detail="Can only delete campaigns in DRAFT or COMPLETED status",
        )

    await campaign_repo.delete(campaign_id)
    await session.commit()

    logger.info(f"Campaign deleted: {campaign_id}")


@router.post("/{campaign_id}/schedule", response_model=CampaignResponse)
async def schedule_campaign(
    campaign_id: UUID,
    data: CampaignSchedule,
    session: AsyncSession = Depends(get_session),
):
    campaign_repo = CampaignRepository(session)
    contact_repo = CampaignContactRepository(session)

    campaign = await campaign_repo.get_by_id(campaign_id)
    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status != CampaignStatus.DRAFT:
        raise BadRequestError(
            detail="Can only schedule campaigns in DRAFT status",
        )

    if campaign.total_contacts == 0:
        # Fallback: Double check actual count in case of sync issues
        actual_count = await contact_repo.count_all(campaign_id)
        if actual_count > 0:
            campaign.total_contacts = actual_count
            session.add(campaign)
        else:
            raise BadRequestError(
                detail="Cannot schedule campaign with no contacts",
            )

    now = get_utc_now()
    if data.scheduled_at <= now:
        raise BadRequestError(
            detail="Scheduled time must be in the future",
        )

    campaign.scheduled_at = data.scheduled_at
    campaign.status = CampaignStatus.SCHEDULED
    campaign.updated_at = now
    session.add(campaign)

    await session.commit()

    logger.info(f"Campaign scheduled: {campaign_id} at {data.scheduled_at}")
    return campaign


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign_now(
    campaign_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    campaign_repo = CampaignRepository(session)
    contact_repo = CampaignContactRepository(session)

    campaign = await campaign_repo.get_by_id(campaign_id)
    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
        raise BadRequestError(
            detail="Can only start campaigns in DRAFT or SCHEDULED status",
        )

    if campaign.total_contacts == 0:
        actual_count = await contact_repo.count_all(campaign_id)
        if actual_count > 0:
            campaign.total_contacts = actual_count
            session.add(campaign)
        else:
            raise BadRequestError(
                detail="Cannot start campaign with no contacts",
            )

    try:
        # Publish campaign start event to NATS
        await broker.publish(
            str(campaign_id),
            subject="campaigns.start",
            stream="campaigns",
        )
        logger.info(f"Campaign start published: {campaign_id}")
    except Exception as e:
        logger.error(f"Failed to publish campaign start: {e}")
        raise ServiceUnavailableError(detail="Failed to start campaign")

    return campaign


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get_by_id(campaign_id)
    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status != CampaignStatus.RUNNING:
        raise BadRequestError(detail="Can only pause running campaigns")

    campaign.status = CampaignStatus.PAUSED
    campaign.updated_at = get_utc_now()
    session.add(campaign)

    await session.commit()

    # Notify via NATS for worker to handle pause
    try:
        await broker.publish(
            str(campaign_id),
            subject="campaigns.pause",
            stream="campaigns",
        )
        logger.info(f"Campaign pause published: {campaign_id}")
    except Exception as e:
        logger.warning(f"Failed to publish campaign pause event: {e}")

    logger.info(f"Campaign paused: {campaign_id}")
    return campaign


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    campaign_repo = CampaignRepository(session)
    campaign = await campaign_repo.get_by_id(campaign_id)
    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status != CampaignStatus.PAUSED:
        raise BadRequestError(detail="Can only resume paused campaigns")

    try:
        await broker.publish(
            str(campaign_id),
            subject="campaigns.resume",
            stream="campaigns",
        )
        logger.info(f"Campaign resume published: {campaign_id}")
    except Exception as e:
        logger.error(f"Failed to publish campaign resume: {e}")
        raise ServiceUnavailableError(detail="Failed to resume campaign")

    return campaign


@router.get("/{campaign_id}/stats", response_model=CampaignResponse)
async def get_campaign_stats(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed campaign statistics.
    """
    campaign = await CampaignRepository(session).get_by_id(campaign_id)
    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    return campaign


@router.get("/{campaign_id}/contacts", response_model=list[CampaignContactResponse])
async def get_campaign_contacts(
    campaign_id: UUID,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    campaign = await CampaignRepository(session).get_by_id(campaign_id)
    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    links = await CampaignContactRepository(session).get_campaign_contacts(
        campaign_id, limit, offset
    )
    return links


@router.post("/{campaign_id}/contacts/import", response_model=ContactImportResult)
async def import_contacts_from_file(
    campaign_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    import_service: ContactImportService = Depends(get_contact_import_service),
):
    """Import contacts from CSV or Excel file."""
    campaign = await CampaignRepository(session).get_by_id(campaign_id)

    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status != CampaignStatus.DRAFT:
        raise BadRequestError(
            detail="Can only import contacts to DRAFT campaigns",
        )

    content = await file.read()

    result = await import_service.import_file(campaign_id, content, file.filename)

    if result.errors and any("Unsupported file format" in e for e in result.errors):
        raise BadRequestError(detail="Unsupported file format. Use .csv, .xlsx or .xls")

    logger.info(
        f"Import completed for campaign {campaign_id}: "
        f"{result.imported}/{result.total} contacts"
    )

    return result


@router.post("/{campaign_id}/contacts", response_model=ContactImportResult)
async def add_contacts_manually(
    campaign_id: UUID,
    contacts: list[ContactImport],
    session: AsyncSession = Depends(get_session),
    import_service: ContactImportService = Depends(get_contact_import_service),
):
    """Add contacts manually via API."""
    campaign = await CampaignRepository(session).get_by_id(campaign_id)

    if not campaign:
        raise NotFoundError(detail="Campaign not found")

    if campaign.status != CampaignStatus.DRAFT:
        raise BadRequestError(
            detail="Can only add contacts to DRAFT campaigns",
        )

    result = await import_service.add_contacts_manual(campaign_id, contacts)

    logger.info(
        f"Manual add completed for campaign {campaign_id}: "
        f"{result.imported}/{result.total} contacts"
    )

    return result
