import os
import uuid

import aiofiles
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from loguru import logger
from src.core.dependencies import get_uow
from src.core.uow import UnitOfWork
from src.core.websocket import manager
from src.schemas import MessageCreate, MessageSendResponse, WhatsAppMessage
from src.worker import handle_media_send_task, handle_messages_task

router = APIRouter(tags=["Messages"])

TEMP_MEDIA_DIR = "temp_media"
os.makedirs(TEMP_MEDIA_DIR, exist_ok=True)


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
    """
    request_id = str(uuid.uuid4())

    message_body = data.body
    if data.type == "template" and data.template_id:
        message_body = str(data.template_id)

    message_obj = WhatsAppMessage(
        phone_number=data.phone_number,
        type=data.type,
        body=message_body,
        request_id=request_id,
        reply_to_message_id=data.reply_to_message_id,
    )

    await handle_messages_task.kiq(message_obj)

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
            while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                await out_file.write(content)

        # Get file size for validation AFTER saving (or check Content-Length header)
        file_size = os.path.getsize(file_path)
        max_size = 100 * 1024 * 1024

        if file_size > max_size:
            os.remove(file_path)  # Clean up
            raise HTTPException(status_code=413, detail="File too large")

        mime_type = file.content_type or "application/octet-stream"

        # Pass the PATH, not the bytes
        await handle_media_send_task.kiq(
            phone_number=phone_number,
            file_path=file_path,
            filename=file.filename,
            mime_type=mime_type,
            caption=caption,
            request_id=request_id,
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
