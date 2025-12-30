import uuid

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from loguru import logger

from src.core.websocket import manager
from src.schemas import WhatsAppMessage
from src.worker import handle_messages_task

router = APIRouter(tags=["Messages"])


@router.websocket("/ws/messages")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.post("/send_message/{phone}")
async def send_message(
    request: Request,
    phone: str,
    type: str = "text",
    text: str = "This is a test message from the API.",
):
    request_id = str(uuid.uuid4())

    message_obj = WhatsAppMessage(
        phone_number=phone, type=type, body=text, request_id=request_id
    )

    try:
        await handle_messages_task.kiq(message_obj)
    except Exception as e:
        logger.error(f"Failed to publish to Redis: {e}")
        return {"status": "error", "detail": "Internal Broker Error"}

    return {"status": "sent", "request_id": request_id}
