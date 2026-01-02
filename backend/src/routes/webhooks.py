import hashlib
import hmac
import json
from typing import Optional

from fastapi import APIRouter, Header, Query, Request, Response, status
from src.core.config import settings
from src.core.exceptions import AuthError, BadRequestError
from src.schemas import WebhookEvent
from src.worker import handle_raw_webhook_task

router = APIRouter(prefix="/webhook", tags=["Webhooks"])


def verify_signature(raw_body: bytes, signature: str | None) -> None:
    if not settings.META_APP_SECRET:
        return

    if not signature:
        raise AuthError(detail="Missing X-Hub-Signature-256 header")

    parts = signature.split("=")
    if len(parts) != 2 or parts[0] != "sha256":
        raise AuthError(detail="Invalid signature format")

    signature_hash = parts[1]

    mac = hmac.new(
        key=settings.META_APP_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    )
    expected_hash = mac.hexdigest()

    if not hmac.compare_digest(expected_hash, signature_hash):
        raise AuthError(detail="Invalid signature")


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")

    raise AuthError(detail="Invalid token")


@router.post("")
async def receive_webhook(
    request: Request, x_hub_signature_256: Optional[str] = Header(default=None)
):
    try:
        raw_body = await request.body()
    except Exception:
        raise BadRequestError(detail="Failed to read request body")

    verify_signature(raw_body, x_hub_signature_256)

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise BadRequestError(detail="Invalid JSON")

    event = WebhookEvent(payload=data)
    await handle_raw_webhook_task.kiq(event)

    return Response(status_code=status.HTTP_200_OK, content="ok")
