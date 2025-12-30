import uuid

from fastapi import APIRouter, Request
from loguru import logger

from src.schemas import WabaSyncRequest
from src.worker import handle_account_sync_task

router = APIRouter(prefix="", tags=["WABA"])


@router.post("/waba/sync")
async def trigger_waba_sync(request: Request):
    """Sends a command to the worker to update data from Meta."""
    request_id = str(uuid.uuid4())
    sync_request = WabaSyncRequest(request_id=request_id)

    try:
        await handle_account_sync_task.kiq(sync_request)
    except Exception as e:
        logger.error(f"Failed to publish to Redis: {e}")
        return {"status": "error", "detail": "Internal Broker Error"}

    return {"status": "sync_started", "request_id": request_id}
