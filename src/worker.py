import httpx, asyncio

from faststream import FastStream
from faststream.redis import RedisBroker
from src.schemas import WhatsAppMessage
from src.logger import setup_logging
from src.config import settings

logger = setup_logging()

broker = RedisBroker(settings.REDIS_URL)
app = FastStream(broker)

async def send_whatsapp_message(phone: str):
    url = f"{settings.META_URL}/{settings.META_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.META_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": {
                "code": "en_US"
            }
        }
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

@broker.subscriber("whatsapp_messages")
async def handle_messages(message: WhatsAppMessage):
    with logger.contextualize(request_id=message.request_id):
        logger.info(f"Received message request for phone: {message.phone}")

        try:
            result = await send_whatsapp_message(message.phone)
            logger.success(
                f"Message sent successfully. Meta Response: {result}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.exception(f"Failed to send message to {message.phone}")
            