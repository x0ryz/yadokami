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


@router.post("/waba/account", response_model=WabaAccountResponse)
async def create_or_update_waba_account(
    data: WabaAccountRequest, uow: UnitOfWork = Depends(get_uow)
):
    """
    Створює або оновлює дані WABA акаунту.
    Оскільки в системі може бути лише один акаунт, цей метод перевіряє наявність
    існуючого запису і оновлює його, або створює новий.
    """
    async with uow:
        # Перевіряємо, чи вже існує акаунт
        account = await uow.waba.get_account()

        if account:
            # Оновлюємо існуючий
            account.waba_id = data.waba_id
            account.name = data.name
            uow.waba.add(account)
        else:
            # Створюємо новий
            account = WabaAccount(waba_id=data.waba_id, name=data.name)
            uow.waba.add(account)

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
        raise ServiceUnavailableError(
            detail=f"Failed to enqueue sync task. Error: {e}")

    return {
        "status": "sync_started",
        "request_id": request_id,
        "message": "WABA sync initiated",
    }
