import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import settings


def is_transient_error(exception):
    """Повертає True, якщо помилка тимчасова (мережа або 5xx від сервера)"""
    if isinstance(exception, httpx.HTTPStatusError):
        return (
            exception.response.status_code >= 500
            or exception.response.status_code == 429
        )
    return isinstance(
        exception, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)
    )


class MetaClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = settings.META_URL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error),
        reraise=True,
    )
    async def send_message(self, phone_id: str, data: dict):
        """Send a message to a phone number using Meta Graph API."""
        url = f"{self.base_url}/{phone_id}/messages"
        resp = await self.client.post(url, json=data)
        resp.raise_for_status()
        return resp.json()

    async def fetch_account_info(self, waba_id: str):
        """Fetch WABA account information from Meta Graph API."""
        url = f"{self.base_url}/{waba_id}"
        params = {"fields": "name,account_review_status,business_verification_status"}

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def fetch_phone_numbers(self, waba_id: str):
        """Fetch WABA phone numbers from Meta Graph API."""
        url = f"{self.base_url}/{waba_id}/phone_numbers"

        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_media_url(self, media_id: str) -> str:
        """Fetch media URL from Meta Graph API."""
        url = f"{self.base_url}/{media_id}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json().get("url")

    async def download_media_file(self, media_url: str) -> bytes:
        """Download media file from Meta Graph API."""
        resp = await self.client.get(media_url)
        resp.raise_for_status()
        return resp.content

    async def fetch_templates(self, waba_id: str):
        """Fetch message template for a WABA account."""
        url = f"{self.base_url}/{waba_id}/message_templates"
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json()
