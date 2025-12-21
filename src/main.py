import uuid

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from faststream.redis import RedisBroker
from sqladmin import Admin

from src.clients.meta import MetaClient
from src.core.config import settings
from src.core.database import engine
from src.core.logger import setup_logging
from src.schemas import WebhookEvent

logger = setup_logging()
app = FastAPI()
admin = Admin(app, engine, title="Jidoka Admin")


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        return int(hub_challenge or 0)

    raise HTTPException(status_code=403, detail="Invalid token")


@app.post("/webhook")
async def receive_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}

    async with RedisBroker(settings.REDIS_URL) as broker:
        await broker.publish(WebhookEvent(payload=data), channel="raw_webhooks")

    return {"status": "ok"}


@app.post("/send_message/{phone}")
async def send_message(
    phone: str, type: str = "text", text: str = "This is a test message from the API."
):
    request_id = str(uuid.uuid4())

    async with RedisBroker(settings.REDIS_URL) as broker:
        logger.info("New API request received", request_id=request_id)

        await broker.publish(
            {
                "phone_number": phone,
                "type": type,
                "body": text,
                "request_id": request_id,
            },
            channel="whatsapp_messages",
        )

        return {"status": "sent", "request_id": request_id}


@app.post("/waba/sync")
async def trigger_waba_sync():
    """Sends a command to the worker to update data from Meta."""
    request_id = str(uuid.uuid4())

    async with RedisBroker(settings.REDIS_URL) as broker:
        await broker.publish({"request_id": request_id}, channel="sync_account_data")

    return {"status": "sync_started", "request_id": request_id}


@app.get("/media_proxy/{media_id}", name="media_proxy")
async def media_proxy(media_id: str):
    """Проксі для завантаження медіа файлів з Meta"""
    headers = {
        "Authorization": f"Bearer {settings.META_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        meta_client = MetaClient(client)
        try:
            media_url = await meta_client.get_media_url(media_id)
            content = await meta_client.download_media_file(media_url)
            return Response(content)
        except Exception as e:
            # Можна повернути заглушку або 404
            return Response(content=f"Error: {str(e)}", status_code=404)
