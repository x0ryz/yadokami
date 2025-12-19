import uuid
from typing import Union

from fastapi import FastAPI
from sqladmin import Admin
from faststream.redis import RedisBroker

from src.database import engine
from src.admin import LeadAdmin
from src.logger import setup_logging


logger = setup_logging()
app = FastAPI()
admin = Admin(app, engine, title="My Admin")

admin.add_view(LeadAdmin)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

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

    await broker.close()
