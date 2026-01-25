"""
DEPRECATED: Scheduler functionality has been moved to the main worker.
See src/worker/tasks.py (scheduled_messages_checker) and src/worker/routers/messages.py

This file is kept for backward compatibility with existing launch scripts but performs no action.
"""
import asyncio
from loguru import logger

async def process_scheduled_messages():
    """Deprecated entry point."""
    logger.warning("src.worker.scheduler is deprecated. Please run src.worker.main instead.")
    # Sleep forever to keep container alive if needed, but do no work
    while True:
        await asyncio.sleep(3600)

async def main():
    await process_scheduled_messages()

if __name__ == "__main__":
    asyncio.run(main())
