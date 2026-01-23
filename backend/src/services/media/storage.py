import aioboto3

from src.core.config import settings


class AsyncIteratorFile:
    """
    Адаптер, який перетворює асинхронний ітератор (наприклад, від httpx)
    у асинхронний файлоподібний об'єкт для aioboto3.
    """

    def __init__(self, iterator):
        self.iterator = iterator
        self.buffer = b""

    async def read(self, n=-1):
        if n == -1:
            data = [self.buffer]
            async for chunk in self.iterator:
                data.append(chunk)
            self.buffer = b""
            return b"".join(data)

        while len(self.buffer) < n:
            try:
                chunk = await self.iterator.__anext__()
                self.buffer += chunk
            except StopAsyncIteration:
                break

        result = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return result


class StorageService:
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket = settings.R2_BUCKET_NAME

    async def upload_file(
        self, file_content: bytes, object_name: str, content_type: str
    ) -> str:
        """Завантаження байтів (для малих файлів)"""
        async with self.session.client(
            service_name="s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY,
            aws_secret_access_key=settings.R2_SECRET_KEY,
            region_name="auto",
        ) as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=object_name,
                Body=file_content,
                ContentType=content_type,
            )
            return object_name

    async def upload_stream(
        self, file_stream, object_name: str, content_type: str
    ) -> str:
        """
        Потокове завантаження (для великих файлів).
        file_stream може бути AsyncIteratorFile або будь-який об'єкт з async read().
        """
        async with self.session.client(
            service_name="s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY,
            aws_secret_access_key=settings.R2_SECRET_KEY,
            region_name="auto",
        ) as s3:
            await s3.upload_fileobj(
                Fileobj=file_stream,
                Bucket=self.bucket,
                Key=object_name,
                ExtraArgs={"ContentType": content_type},
            )
            return object_name

    def get_public_url(self, object_name: str) -> str:
        """Генерує публічний URL для об'єкта (якщо налаштовано R2_PUBLIC_URL)"""
        if settings.R2_PUBLIC_URL:
            return f"{settings.R2_PUBLIC_URL}/{object_name}"
        # Fallback до bucket URL якщо публічний домен не налаштовано
        return f"https://{self.bucket}.{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{object_name}"

    async def get_presigned_url(self, object_name: str, expires_in: int = 3600) -> str:
        async with self.session.client(
            service_name="s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY,
            aws_secret_access_key=settings.R2_SECRET_KEY,
            region_name="auto",
        ) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_name},
                ExpiresIn=expires_in,
            )
            return url
