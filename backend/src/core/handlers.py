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

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": 500,
            "detail": "Internal Server Error. Please contact support.",
        },
    )
