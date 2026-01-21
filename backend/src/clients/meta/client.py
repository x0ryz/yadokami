import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


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
    def __init__(
        self, client: httpx.AsyncClient, base_url: str = None, token: str = None
    ):
        self.client = client
        self.base_url = base_url
        self.token = token

    def _get_headers(self, existing_headers: dict = None):
        headers = existing_headers or {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error),
        reraise=True,
    )
    async def send_message(
        self, phone_id: str, data: dict, idempotency_key: str = None
    ):
        """Send a message to a phone number using Meta Graph API."""
        url = f"{self.base_url}/{phone_id}/messages"

        headers = self._get_headers()
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        resp = await self.client.post(url, json=data, headers=headers)
        logger.info(f"Meta API send_message status: {resp.status_code} | URL: {url}")

        if resp.status_code >= 400:
            logger.error(f"Meta API Error Response: {resp.text}")
        resp.raise_for_status()
        return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error),
        reraise=True,
    )
    async def upload_media(
        self, phone_id: str, file_bytes: bytes, mime_type: str, filename: str
    ) -> str:
        """Upload media file to WhatsApp Business API."""
        url = f"{self.base_url}/{phone_id}/media"

        files = {"file": (filename, file_bytes, mime_type)}
        data = {"messaging_product": "whatsapp"}

        headers = self._get_headers()

        resp = await self.client.post(url, files=files, data=data, headers=headers)
        logger.info(f"Meta API upload_media status: {resp.status_code} | URL: {url}")
        if resp.status_code >= 400:
            logger.error(f"Meta API Upload Error: {resp.text}")
        resp.raise_for_status()

        result = resp.json()
        media_id = result.get("id")

        if not media_id:
            raise ValueError("No media ID returned from Meta API")

        return media_id

    async def fetch_account_info(self, waba_id: str):
        """Fetch WABA account information from Meta Graph API."""
        url = f"{self.base_url}/{waba_id}"
        params = {"fields": "name,account_review_status,business_verification_status"}

        resp = await self.client.get(url, params=params, headers=self._get_headers())
        logger.info(
            f"Meta API fetch_account_info response: {resp.status_code} for WABA: {waba_id}"
        )
        resp.raise_for_status()
        return resp.json()

    async def fetch_phone_numbers(self, waba_id: str):
        """Fetch WABA phone numbers from Meta Graph API."""
        url = f"{self.base_url}/{waba_id}/phone_numbers"

        resp = await self.client.get(url, headers=self._get_headers())
        logger.info(
            f"Meta API fetch_phone_numbers response: {resp.status_code} for WABA: {waba_id}"
        )
        resp.raise_for_status()
        return resp.json()

    async def get_media_url(self, media_id: str) -> str:
        """Fetch media URL from Meta Graph API."""
        url = f"{self.base_url}/{media_id}"
        resp = await self.client.get(url, headers=self._get_headers())
        logger.info(
            f"Meta API get_media_url response: {resp.status_code} for Media ID: {media_id}"
        )
        resp.raise_for_status()
        return resp.json().get("url")

    async def stream_media_file(self, media_url: str):
        """Return a generator for streaming reading"""
        async with self.client.stream(
            "GET", media_url, headers=self._get_headers()
        ) as response:
            logger.info(
                f"Meta API stream_media_file response: {response.status_code} for URL: {media_url}"
            )
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def fetch_templates(self, waba_id: str):
        """Fetch message template for a WABA account."""
        url = f"{self.base_url}/{waba_id}/message_templates"
        resp = await self.client.get(url, headers=self._get_headers())
        logger.info(
            f"Meta API fetch_templates response: {resp.status_code} for WABA: {waba_id}"
        )
        resp.raise_for_status()
        return resp.json()
