import sys
from loguru import logger
from src.config import settings


def setup_logging():
    logger.remove()

    if settings.DEBUG:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            serialize=True,
            format="{time} {level} {message}"
        )

    return logger
