import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.broker import broker
from src.core.dependencies import get_session
from src.core.exceptions import ServiceUnavailableError
from src.models import WabaAccount
from src.repositories.waba import WabaPhoneRepository, WabaRepository
from src.schemas import (
    WabaAccountRequest,
    WabaAccountResponse,
    WabaPhoneNumbersResponse,
    WabaSyncRequest,
    WabaSyncResponse,
)

router = APIRouter(prefix="", tags=["WABA"])


@router.get("/waba/settings", response_model=WabaAccountResponse)
async def get_waba_settings(session: AsyncSession = Depends(get_session)):
    """
    Отримує поточні налаштування WABA (без чутливих даних).
    """
    account = await WabaRepository(session).get_credentials()
    if not account:
        raise HTTPException(status_code=404, detail="WABA account not found")
    return account


@router.post("/waba/settings", response_model=WabaAccountResponse)
async def update_waba_settings(
    settings: WabaAccountRequest, session: AsyncSession = Depends(get_session)
):
    """
    Створює або оновлює налаштування WABA (ID, Токени, Секрети).
    Дані автоматично шифруються при збереженні в БД.
    """
    repo = WabaRepository(session)
    account = await repo.get_credentials()

    if not account:
        account = WabaAccount(
            waba_id=settings.waba_id,
            name=settings.name,
        )
        session.add(account)

    account.waba_id = settings.waba_id
    account.name = settings.name

    if settings.access_token:
        account.access_token = settings.access_token
    if settings.app_secret:
        account.app_secret = settings.app_secret
    if settings.verify_token:
        account.verify_token = settings.verify_token
    if settings.graph_api_version:
        account.graph_api_version = settings.graph_api_version

    await session.commit()
    await session.refresh(account)

    return account


@router.post("/waba/sync", response_model=WabaSyncResponse)
async def trigger_waba_sync(request: Request):
    """Sends a command to the worker to update data from Meta."""
    request_id = str(uuid.uuid4())
    sync_request = WabaSyncRequest(request_id=request_id)

    try:
        # Publish sync request to NATS
        await broker.publish(
            sync_request.model_dump(),
            subject="sync.account_data",
        )
    except Exception as e:
        raise ServiceUnavailableError(detail=f"Failed to enqueue sync task. Error: {e}")

    return {
        "status": "sync_started",
        "request_id": request_id,
        "message": "WABA sync initiated",
    }


@router.get("/waba/phone-numbers", response_model=WabaPhoneNumbersResponse)
async def get_waba_phone_numbers(session: AsyncSession = Depends(get_session)):
    """Get a list of available phone numbers."""
    phone_numbers = await WabaPhoneRepository(session).get_all_phones()
    return {"phone_numbers": phone_numbers}
