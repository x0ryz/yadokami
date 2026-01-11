from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from loguru import logger
from src.core.dependencies import get_contact_import_service, get_uow
from src.core.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError
from src.core.uow import UnitOfWork
from src.models import CampaignStatus, get_utc_now
from src.schemas import (
    CampaignContactResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignSchedule,
    CampaignStats,
    CampaignUpdate,
    ContactImport,
    ContactImportResult,
)
from src.services.campaign.importer import ContactImportService
from src.worker import handle_campaign_resume_task, handle_campaign_start_task

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Create a new campaign.

    - **name**: Campaign name (required)
    - **message_type**: "text" or "template" (default: template)
    - **template_id**: UUID of template (required if message_type=template)
    - **message_body**: Text body (required if message_type=text)
    """
    async with uow:
        # Validation
        if data.message_type == "template" and not data.template_id:
            raise BadRequestError(
                detail="template_id is required when message_type is 'template'"
            )

        if data.message_type == "text" and not data.message_body:
            raise BadRequestError(
                detail="message_body is required when message_type is 'text'",
            )

        # Verify template exists if provided
        if data.template_id:
            template = await uow.templates.get_by_id(data.template_id)
            if not template:
                raise NotFoundError(
                    detail=f"Template with id {data.template_id} not found",
                )
            if template.status != "APPROVED":
                raise BadRequestError(
                    detail="Template must be APPROVED",
                )

        # Create campaign
        campaign = await uow.campaigns.create(
            name=data.name,
            message_type=data.message_type,
            template_id=data.template_id,
            message_body=data.message_body,
            status=CampaignStatus.DRAFT,
        )

        logger.info(f"Campaign created: {campaign.id} - {campaign.name}")

        return campaign


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    status: CampaignStatus | None = None,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    List campaigns filtered by status. Newest scheduled/created first.
    """
    async with uow:
        campaigns = await uow.campaigns.list_with_status(status=status)
        return campaigns


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Get campaign by ID.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Update campaign details.

    Only campaigns in DRAFT status can be updated.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        if campaign.status != CampaignStatus.DRAFT:
            raise BadRequestError(
                detail="Can only update campaigns in DRAFT status",
            )

        # Update fields
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(campaign, key, value)

        campaign.updated_at = get_utc_now()
        uow.session.add(campaign)

        logger.info(f"Campaign updated: {campaign_id}")

        return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Delete a campaign.

    Only campaigns in DRAFT status can be deleted.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.COMPLETED]:
            raise BadRequestError(
                detail="Can only delete campaigns in DRAFT or COMPLETED status",
            )

        await uow.campaigns.delete(campaign_id)

        logger.info(f"Campaign deleted: {campaign_id}")


@router.post("/{campaign_id}/schedule", response_model=CampaignResponse)
async def schedule_campaign(
    campaign_id: UUID,
    data: CampaignSchedule,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Schedule a campaign to run at a specific time.

    Campaign must be in DRAFT status and have contacts.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        if campaign.status != CampaignStatus.DRAFT:
            raise BadRequestError(
                detail="Can only schedule campaigns in DRAFT status",
            )

        if campaign.total_contacts == 0:
            raise BadRequestError(
                detail="Cannot schedule campaign with no contacts",
            )

        # Validate scheduled time is in the future
        now = get_utc_now()
        if data.scheduled_at <= now:
            raise BadRequestError(
                detail="Scheduled time must be in the future",
            )

        campaign.scheduled_at = data.scheduled_at
        campaign.status = CampaignStatus.SCHEDULED
        campaign.updated_at = now
        uow.session.add(campaign)

        logger.info(
            f"Campaign scheduled: {campaign_id} at {data.scheduled_at}")

        return campaign


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign_now(
    campaign_id: UUID,
    request: Request,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Start campaign immediately.

    Campaign must be in DRAFT or SCHEDULED status and have contacts.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
            raise BadRequestError(
                detail="Can only start campaigns in DRAFT or SCHEDULED status",
            )

        if campaign.total_contacts == 0:
            raise BadRequestError(
                detail="Cannot start campaign with no contacts",
            )

        try:
            await handle_campaign_start_task.kiq(str(campaign_id))
            logger.info(f"Campaign start published: {campaign_id}")
        except Exception as e:
            logger.error(f"Failed to publish campaign start: {e}")
            raise ServiceUnavailableError(
                detail="Failed to start campaign",
            )

        # Status will be updated by worker
        return campaign


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Pause a running campaign.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        if campaign.status != CampaignStatus.RUNNING:
            raise BadRequestError(
                detail="Can only pause running campaigns",
            )

        campaign.status = CampaignStatus.PAUSED
        campaign.updated_at = get_utc_now()
        uow.session.add(campaign)

        logger.info(f"Campaign paused: {campaign_id}")

        return campaign


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: UUID,
    request: Request,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Resume a paused campaign.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        if campaign.status != CampaignStatus.PAUSED:
            raise BadRequestError(
                detail="Can only resume paused campaigns",
            )

        try:
            await handle_campaign_resume_task.kiq(str(campaign_id))
            logger.info(f"Campaign resume published: {campaign_id}")
        except Exception as e:
            logger.error(f"Failed to publish campaign resume: {e}")
            raise ServiceUnavailableError(
                detail="Failed to resume campaign",
            )

        return campaign


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
async def get_campaign_stats(
    campaign_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Get detailed campaign statistics.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        # Calculate progress
        progress = 0.0
        if campaign.total_contacts > 0:
            progress = (campaign.sent_count / campaign.total_contacts) * 100

        return CampaignStats(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            total_contacts=campaign.total_contacts,
            sent_count=campaign.sent_count,
            delivered_count=campaign.delivered_count,
            failed_count=campaign.failed_count,
            progress_percent=round(progress, 2),
            scheduled_at=campaign.scheduled_at,
            started_at=campaign.started_at,
            completed_at=campaign.completed_at,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )


@router.get("/{campaign_id}/contacts", response_model=list[CampaignContactResponse])
async def get_campaign_contacts(
    campaign_id: UUID,
    limit: int = 100,
    offset: int = 0,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Get contacts in a campaign with pagination.
    """
    async with uow:
        campaign = await uow.campaigns.get_by_id(campaign_id)

        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        links = await uow.campaign_contacts.get_campaign_contacts(
            campaign_id, limit, offset
        )

        result = []
        for link in links:
            result.append(
                CampaignContactResponse(
                    id=link.id,
                    contact_id=link.contact_id,
                    phone_number=link.contact.phone_number,
                    name=link.contact.name,
                    status=link.status,
                    error_message=link.error_message,
                    retry_count=link.retry_count,
                )
            )

        return result


@router.post("/{campaign_id}/contacts/import", response_model=ContactImportResult)
async def import_contacts_from_file(
    campaign_id: UUID,
    file: UploadFile = File(...),
    uow: UnitOfWork = Depends(get_uow),
    import_service: ContactImportService = Depends(get_contact_import_service),
):
    """
    Import contacts from CSV or Excel file.

    **CSV Format:**
    ```
    phone_number,name,tags
    +380671234567,John Doe,vip;active
    0671234568,Jane Smith,new
    ```

    **Excel Format:**
    Same columns as CSV, first row must be headers.

    **Supported formats:** .csv, .xlsx, .xls
    """
    async with uow:
        # Check campaign exists
        campaign = await uow.campaigns.get_by_id(campaign_id)
        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        # Only allow import for DRAFT campaigns
        if campaign.status != CampaignStatus.DRAFT:
            raise BadRequestError(
                detail="Can only import contacts to DRAFT campaigns",
            )

        # Read file
        content = await file.read()

        # Determine file type
        filename = file.filename.lower()

        if filename.endswith(".csv"):
            result = await import_service.import_from_csv(campaign_id, content)
        elif filename.endswith((".xlsx", ".xls")):
            result = await import_service.import_from_excel(campaign_id, content)
        else:
            raise BadRequestError(
                detail="Unsupported file format. Use .csv, .xlsx or .xls",
            )

        logger.info(
            f"Import completed for campaign {campaign_id}: "
            f"{result.imported}/{result.total} contacts"
        )

        return result


@router.post("/{campaign_id}/contacts", response_model=ContactImportResult)
async def add_contacts_manually(
    campaign_id: UUID,
    contacts: list[ContactImport],
    uow: UnitOfWork = Depends(get_uow),
    import_service: ContactImportService = Depends(get_contact_import_service),
):
    """
    Add contacts manually via API (without file upload).

    Example:
    ```json
    [
      {
        "phone_number": "+380671234567",
        "name": "John Doe",
        "tags": ["vip", "active"]
      },
      {
        "phone_number": "0671234568",
        "name": "Jane Smith",
        "tags": ["new"]
      }
    ]
    ```
    """
    async with uow:
        # Check campaign exists
        campaign = await uow.campaigns.get_by_id(campaign_id)
        if not campaign:
            raise NotFoundError(detail="Campaign not found")

        # Only allow import for DRAFT campaigns
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
