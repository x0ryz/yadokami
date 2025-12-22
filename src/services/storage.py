import aioboto3

from src.core.config import settings


class StorageService:
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket = settings.R2_BUCKET_NAME

    async def upload_file(
        self, file_content: bytes, object_name: str, content_type: str
    ) -> str:
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
