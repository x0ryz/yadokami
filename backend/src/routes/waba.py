import uuid

from fastapi import APIRouter, Request
from src.core.exceptions import ServiceUnavailableError
from src.schemas import (
    WabaSyncRequest,
    WabaSyncResponse,
)
from src.worker import handle_account_sync_task

router = APIRouter(prefix="", tags=["WABA"])


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
