import uuid

from fastapi import APIRouter, Depends, Request
from src.core.dependencies import get_uow
from src.core.exceptions import ServiceUnavailableError
from src.core.uow import UnitOfWork
from src.models import WabaAccount
from src.schemas import (
    WabaAccountRequest,
    WabaAccountResponse,
    WabaSyncRequest,
    WabaSyncResponse,
)
from src.worker import handle_account_sync_task

router = APIRouter(prefix="", tags=["WABA"])


@router.post("/waba/settings", response_model=WabaAccountResponse)
async def update_waba_settings(
    settings: WabaAccountRequest, uow: UnitOfWork = Depends(get_uow)
):
    """
    Створює або оновлює налаштування WABA (ID, Токени, Секрети).
    Дані автоматично шифруються при збереженні в БД.
    """
    async with uow:
        account = await uow.waba.get_account()

        if not account:
            account = WabaAccount(
                waba_id=settings.waba_id,
                name=settings.name,
            )
            uow.waba.add(account)

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

        await uow.commit()

        await uow.session.refresh(account)

        return account


@router.post("/waba/sync", response_model=WabaSyncResponse)
async def trigger_waba_sync(request: Request):
    """Sends a command to the worker to update data from Meta."""
    request_id = str(uuid.uuid4())
    sync_request = WabaSyncRequest(request_id=request_id)

    try:
        await handle_account_sync_task.kiq(sync_request)
    except Exception as e:
        raise ServiceUnavailableError(detail=f"Failed to enqueue sync task. Error: {e}")

    return {
        "status": "sync_started",
        "request_id": request_id,
        "message": "WABA sync initiated",
    }
