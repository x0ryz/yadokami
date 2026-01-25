import os
import tempfile
import uuid

import aiofiles
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from loguru import logger

from src.core.broker import broker
from src.core.websocket import manager
from src.schemas import MessageCreate, MessageSendResponse, WhatsAppMessage

router = APIRouter(tags=["Messages"])

TEMP_MEDIA_DIR = tempfile.gettempdir()


@router.websocket("/ws/messages")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.post(
    "/messages",
    response_model=MessageSendResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_message(data: MessageCreate):
    """
    Send a WhatsApp message asynchronously.

    - **text**: Send regular text message
    - **template**: Send template message (template_id required)
    - **scheduled_at**: Optional ISO 8601 datetime to schedule message for future delivery
    """
    from src.models.base import get_utc_now
    request_id = str(uuid.uuid4())

    message_body = data.body
    if data.type == "template" and data.template_id:
        message_body = str(data.template_id)

    # Check if message is scheduled for future
    if data.scheduled_at:
        now = get_utc_now()
        if data.scheduled_at <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time must be in the future"
            )
        
        # For scheduled messages, we'll save them directly to DB
        # instead of publishing to NATS immediately
        # A background scheduler will handle sending them at the right time
        await broker.publish(
            {
                "phone_number": data.phone_number,
                "type": data.type,
                "body": message_body,
                "reply_to_message_id": str(data.reply_to_message_id) if data.reply_to_message_id else None,
                "phone_id": str(data.phone_id) if data.phone_id else None,
                "scheduled_at": data.scheduled_at.isoformat(),
                "request_id": request_id,
            },
            subject="messages.schedule",
        )
        
        return MessageSendResponse(
            status="scheduled", message_id=uuid.uuid4(), request_id=request_id
        )

    # For immediate messages, use existing flow
    message_obj = WhatsAppMessage(
        phone_number=data.phone_number,
        type=data.type,
        body=message_body,
        request_id=request_id,
        reply_to_message_id=data.reply_to_message_id,
    )

    # Publish message to NATS
    await broker.publish(
        message_obj.model_dump(),
        subject="messages.manual_send",
    )

    return MessageSendResponse(
        status="queued", message_id=uuid.uuid4(), request_id=request_id
    )


@router.post(
    "/messages/media",
    response_model=MessageSendResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_media_message(
    phone_number: str = Form(..., description="Recipient phone number"),
    file: UploadFile = File(..., description="Media file to send"),
    caption: str | None = Form(None, description="Optional caption for media"),
):
    """
    Send a media message (image, video, audio, document).

    **Supported file types:**
    - Images: JPEG, PNG, WebP (stickers)
    - Videos: MP4, 3GP
    - Audio: AAC, MP3, OGG Opus (voice notes)
    - Documents: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, etc.

    **Size limits:**
    - Images: 5 MB
    - Videos: 16 MB
    - Audio: 16 MB
    - Documents: 100 MB

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/messages/media" \
      -F "phone_number=380671234567" \
      -F "file=@/path/to/image.jpg" \
      -F "caption=Check this out!"
    ```
    """
    request_id = str(uuid.uuid4())

    # Validate phone number
    if not phone_number or len(phone_number) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number"
        )

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File is required"
        )

    file_ext = os.path.splitext(file.filename)[1]
    saved_filename = f"{request_id}{file_ext}"
    file_path = os.path.join(TEMP_MEDIA_DIR, saved_filename)

    # Read file content
    try:
        # Stream write to disk (better for RAM than read())
        async with aiofiles.open(file_path, "wb") as out_file:
            # Read in 1MB chunks
            while content := await file.read(1024 * 1024):
                await out_file.write(content)

        # Get file size for validation AFTER saving (or check Content-Length header)
        file_size = os.path.getsize(file_path)
        max_size = 100 * 1024 * 1024

        if file_size > max_size:
            os.remove(file_path)  # Clean up
            raise HTTPException(status_code=413, detail="File too large")

        mime_type = file.content_type or "application/octet-stream"

        # Publish media send message to NATS
        await broker.publish(
            {
                "phone_number": phone_number,
                "file_path": file_path,
                "filename": file.filename,
                "mime_type": mime_type,
                "caption": caption,
                "request_id": request_id,
            },
            subject="messages.media_send",
        )

        return MessageSendResponse(
            status="queued", message_id=uuid.uuid4(), request_id=request_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process media upload: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process file upload",
        )


@router.post(
    "/messages/{message_id}/send-now",
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_scheduled_message_now(message_id: str):
    """Send a scheduled message immediately."""
    await broker.publish(
        {"message_id": message_id},
        subject="messages.send_scheduled_now",
    )
    return {"status": "processing"}


@router.delete(
    "/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scheduled_message(message_id: str):
    """Delete a scheduled message."""
    await broker.publish(
        {"message_id": message_id},
        subject="messages.delete_scheduled",
    )
    return None
