from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.core.exceptions import BaseException


async def local_exception_handler(request: Request, exc: BaseException):
    """Обробник для кастомних бізнес-винятків."""
    logger.warning(f"Business error: {exc.message} (Path: {request.url.path})")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "detail": exc.message,
            "payload": exc.payload,
        },
    )


async def global_exception_handler(request: Request, exc: Exception):
    """Глобальний перехоплювач усіх непередбачених помилок (500)."""
    logger.exception(f"Unhandled exception: {exc} (Path: {request.url.path})")

    # Send notification to Telegram
    try:
        from src.clients.telegram import telegram_client
        from src.core.config import settings

        if settings.TG_DEV_ID:
            error_msg = (
                f"<b>500 Internal Server Error</b>\n\n"
                f"<b>Path:</b> {request.url.path}\n"
                f"<b>Error:</b> {str(exc)}\n\n"
                f"Check logs for details."
            )
            # We don't await here to not block the response excessively,
            # but since we are in async context, we SHOULD await it.
            # Ideally this would be a background task, but let's await for simplicity
            # as it's a critical error handling.
            await telegram_client.send_message(settings.TG_DEV_ID, error_msg)
    except Exception as e:
        logger.error(f"Failed to send error notification to Telegram: {e}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": 500,
            "detail": "Internal Server Error. Please contact support.",
        },
    )
