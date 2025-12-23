import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from faststream.redis import RedisBroker
from redis import asyncio as aioredis
from sqladmin import Admin
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import settings
from src.core.database import engine, get_session
from src.core.logger import setup_logging
from src.core.websocket import manager
from src.models import Contact, Message
from src.schemas import WebhookEvent

background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan: Starting up...")

    task = asyncio.create_task(redis_listener())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    yield

    logger.info("Lifespan: Shutting down...")

    for task in background_tasks:
        task.cancel()

    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)


logger = setup_logging()
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

admin = Admin(app, engine, title="Jidoka Admin")


async def redis_listener():
    logger.info("Starting Redis Listener...")
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        pubsub = redis.pubsub()
        await pubsub.subscribe("ws_updates")

        logger.info("Subscribed to 'ws_updates' channel.")

        async for message in pubsub.listen():
            # Логуємо все, що приходить (навіть службові повідомлення підписки)
            # logger.debug(f"Raw Redis event: {message}")

            if message["type"] == "message":
                logger.info(f"Received message data: {message['data']}")
                try:
                    data = json.loads(message["data"])
                    await manager.broadcast(data)
                except Exception as e:
                    logger.error(f"Error broadcasting message: {e}")
    except Exception as e:
        logger.error(f"Redis listener crashed: {e}")


@app.websocket("/ws/messages")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


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


@app.get("/contacts", response_model=list[Contact])
async def get_contacts(session: AsyncSession = Depends(get_session)):
    statement = select(Contact).order_by(desc(Contact.updated_at))
    result = await session.exec(statement)
    contacts = result.all()
    return contacts


@app.get("/contacts/{contact_id}/messages", response_model=list[Message])
async def get_chat_history(
    contact_id: UUID,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    contact = await session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    statement = (
        select(Message)
        .where(Message.contact_id == contact_id)
        .options(selectinload(Message.media_files))
        .order_by(desc(Message.created_at))
        .offset(offset)
        .limit(limit)
    )

    result = await session.exec(statement)
    messages = result.all()
    return list(reversed(messages))
