import httpx
import asyncio

from faststream import FastStream, Context, ContextRepo
from faststream.redis import RedisBroker
from sqlmodel import select

from src.schemas import WhatsAppMessage, WabaSyncRequest
from src.database import async_session_maker
from src.logger import setup_logging
from src.config import settings
from src.models import WabaAccount

logger = setup_logging()

broker = RedisBroker(settings.REDIS_URL)
app = FastStream(broker)


@app.on_startup
async def setup_http_client(context: ContextRepo):
    client = httpx.AsyncClient(
        timeout=10.0,
        headers={
            "Authorization": f"Bearer {settings.META_TOKEN}",
            "Content-Type": "application/json"
        }
    )

    context.set_global("http_client", client)
    logger.info("HTTPX Client initialized")


@app.after_shutdown
async def close_http_client(context: ContextRepo):
    client = context.get("http_client")
    if client:
        await client.aclose()
        logger.info("HTTPX Client closed")


async def send_whatsapp_message(payload: WhatsAppMessage, client: httpx.AsyncClient):
    url = f"{settings.META_URL}/{settings.META_PHONE_ID}/messages"

    if payload.type == "text":
        data = {
            "messaging_product": "whatsapp",
            "to": payload.phone,
            "type": "text",
            "text": {"body": payload.body}
        }
    else:
        data = {
            "messaging_product": "whatsapp",
            "to": payload.phone,
            "type": "template",
            "template": {
                "name": payload.body,
                "language": {"code": "en_US"}
            }
        }

    resp = await client.post(url, json=data)
    resp.raise_for_status()
    return resp.json()


async def fetch_waba_account_info(waba_id: str, client: httpx.AsyncClient):
    """Fetch WABA account information from Meta Graph API."""
    url = f"{settings.META_URL}/{waba_id}"
    params = {"fields": "name,account_review_status,business_verification_status"}

    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


@broker.subscriber("whatsapp_messages")
async def handle_messages(message: WhatsAppMessage, client: httpx.AsyncClient = Context("http_client")):
    with logger.contextualize(request_id=message.request_id):
        logger.info(f"Received message request for phone: {message.phone}")

        try:
            result = await send_whatsapp_message(message, client)
            logger.success(
                f"Message sent successfully. Meta Response: {result}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.exception(f"Failed to send message to {message.phone}")


@broker.subscriber("sync_account_data")
async def handle_account_sync(message: WabaSyncRequest, client: httpx.AsyncClient = Context("http_client")):
    request_id = message.request_id

    with logger.contextualize(request_id=request_id):
        logger.info(f"Starting sync from database...")

        async with async_session_maker() as session:
            result = await session.exec(select(WabaAccount))
            waba_account = result.first()

            if not waba_account:
                logger.warning("No WABA accounts found in the database.")
                return
            
            current_waba_id = waba_account.waba_id
            logger.info(f"Syncing WABA account ID: {current_waba_id}")

        try:
            account_info = await fetch_waba_account_info(current_waba_id, client)

            waba_account.name = account_info.get("name")
            waba_account.account_review_status = account_info.get("account_review_status")
            waba_account.business_verification_status = account_info.get("business_verification_status")

            session.add(waba_account)
            await session.commit()
            await session.refresh(waba_account)
            logger.success(f"Synced account '{waba_account.name}' successfully.")
        except Exception as e:
            logger.exception(f"Failed to sync WABA ID {current_waba_id}")
