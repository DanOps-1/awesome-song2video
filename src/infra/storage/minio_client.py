"""MinIO/S3 对象存储封装。"""

from __future__ import annotations

from pathlib import Path

from minio import Minio

from src.infra.config.settings import get_settings


class MediaClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.media_bucket
        endpoint = settings.minio_endpoint.replace("http://", "").replace("https://", "")
        self.client = Minio(endpoint, secure=settings.minio_endpoint.startswith("https"))

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_audio(self, object_name: str, file_path: Path) -> str:
        self.client.fput_object(self.bucket, object_name, str(file_path))
        return object_name

    def generate_presigned(self, object_name: str) -> str:
        return self.client.presigned_get_object(self.bucket, object_name)


media_client = MediaClient()
