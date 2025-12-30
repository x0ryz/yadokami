import json

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from src.core.config import settings
from src.schemas import WebhookEvent
from src.worker import handle_raw_webhook_task

router = APIRouter(prefix="/webhook", tags=["Webhooks"])


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")


@router.post("")
async def receive_webhook(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content="Invalid JSON")

    event = WebhookEvent(payload=data)

    try:
        await handle_raw_webhook_task.kiq(event)
    except Exception:
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(status_code=status.HTTP_200_OK, content="ok")
