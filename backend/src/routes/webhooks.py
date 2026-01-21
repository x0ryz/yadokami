import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.broker import broker
from src.core.dependencies import get_session
from src.core.exceptions import AuthError, BadRequestError
from src.repositories.waba import WabaRepository
from src.schemas import WebhookEvent

router = APIRouter(prefix="/webhook", tags=["Webhooks"])


def verify_signature(raw_body: bytes, signature: str | None, app_secret: str) -> None:
    """
    Перевіряє підпис вебхука, використовуючи переданий app_secret.
    """
    if not app_secret:
        logger.critical("META_APP_SECRET is not set! Webhook security is compromised.")
        raise AuthError(detail="Server misconfiguration")

    if not signature:
        logger.warning("Missing X-Hub-Signature-256 header")
        raise AuthError(detail="Missing signature")

    parts = signature.split("=")
    if len(parts) != 2 or parts[0] != "sha256":
        logger.warning(f"Invalid signature format: {signature}")
        raise AuthError(detail="Invalid signature format")

    signature_hash = parts[1]

    mac = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    )
    expected_hash = mac.hexdigest()

    if not hmac.compare_digest(expected_hash, signature_hash):
        logger.error(
            f"Signature mismatch! Expected: {expected_hash}, Got: {signature_hash}"
        )
        raise AuthError(detail="Invalid signature")


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    session: AsyncSession = Depends(get_session),
):
    expected_token = None

    # Fetch the verification token from the database
    account = await WabaRepository(session).get_credentials()
    if account and account.verify_token:
        expected_token = account.verify_token

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Webhook verified successfully via GET challenge")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning(f"Webhook verification failed. Token: {hub_verify_token}")
    raise AuthError(detail="Invalid token")


@router.post("")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    try:
        raw_body = await request.body()
    except Exception as e:
        logger.error(f"Failed to read request body: {e}")
        raise BadRequestError(detail="Failed to read request body")

    app_secret = None

    account = await WabaRepository(session).get_credentials()
    if account and account.app_secret:
        app_secret = account.app_secret

    verify_signature(raw_body, x_hub_signature_256, app_secret)

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Received invalid JSON body")
        raise BadRequestError(detail="Invalid JSON")

    try:
        event = WebhookEvent(payload=data)
        # Publish webhook event to NATS
        await broker.publish(
            event.model_dump(),
            subject="webhooks.raw",
        )

    except Exception as e:
        logger.error(f"Error processing webhook structure: {e}")
        return Response(status_code=status.HTTP_200_OK, content="ok")

    return Response(status_code=status.HTTP_200_OK, content="ok")
