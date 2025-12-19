import uuid

from fastapi import FastAPI, Request, HTTPException
from sqladmin import Admin
from faststream.redis import RedisBroker

from src.database import engine
from src.admin import LeadAdmin
from src.logger import setup_logging
from src.config import settings


logger = setup_logging()
app = FastAPI()
admin = Admin(app, engine, title="My Admin")

admin.add_view(LeadAdmin)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        return int(hub_challenge)

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
async def send_message(phone: str):
    request_id = str(uuid.uuid4())
    broker = RedisBroker("redis://redis:6379")
    await broker.connect()

    logger.info(f"New API request received", request_id=request_id)

    await broker.publish(
        {"phone": phone, "request_id": request_id},
        channel="whatsapp_messages"
    )

    await broker.stop()
