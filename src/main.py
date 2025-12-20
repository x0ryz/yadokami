import uuid

from fastapi import FastAPI, Request, HTTPException, Depends
from sqladmin import Admin
from faststream.redis import RedisBroker

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.database import engine, get_session
from src.models import WabaAccount
# from src.admin import WabaAccountAdmin
from src.logger import setup_logging
from src.config import settings


logger = setup_logging()
app = FastAPI()
admin = Admin(app, engine, title="My Admin")

# admin.add_view(WabaAccountAdmin)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        return int(hub_challenge or 0)

    raise HTTPException(status_code=403, detail="Invalid token")


@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" in value:
            message_data = value["messages"][0]
            phone = message_data["from"]
            text = message_data["text"]["body"]

            print(f"Від: {phone}")
            print(f"Текст: {text}")
    except Exception as e:
        pass

    return {"status": "ok"}


@app.post("/send_message/{phone}")
async def send_message(phone: str, type: str = "text", text: str = "Це тестове повідомлення з API"):
    request_id = str(uuid.uuid4())

    async with RedisBroker(settings.REDIS_URL) as broker:

        logger.info(f"New API request received", request_id=request_id)

        await broker.publish(
            {
                "phone": phone,
                "type": type,
                "body": text,
                "request_id": request_id
            },
            channel="whatsapp_messages"
        )

        return {"status": "sent", "request_id": request_id}


@app.post("/waba/sync")
async def trigger_waba_sync():
    """Відправляє команду воркеру на оновлення даних з Meta."""
    request_id = str(uuid.uuid4())

    async with RedisBroker(settings.REDIS_URL) as broker:
        await broker.publish(
            {"request_id": request_id},
            channel="sync_account_data"
        )

    return {"status": "sync_started", "request_id": request_id}
