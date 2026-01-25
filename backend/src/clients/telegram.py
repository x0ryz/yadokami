import httpx
from loguru import logger

from src.core.config import settings


class TelegramClient:
    def __init__(self):
        self.token = settings.TG_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.client = httpx.AsyncClient(timeout=10.0)

    async def send_message(self, chat_id: int, text: str):
        """Send a message to a Telegram chat."""
        if not self.token:
            logger.warning("Telegram token not set, skipping message sending")
            return

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")

    async def close(self):
        await self.client.aclose()


# Global instance
telegram_client = TelegramClient()
