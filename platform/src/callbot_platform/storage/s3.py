"""S3-compatible object storage (AWS S3, Cloudflare R2, MinIO)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from callbot_platform.config import Settings
from callbot_platform.storage.base import (
    ObjectStorage,
    StoredObject,
    sanitize_object_key,
    validate_object_mime_type,
)

logger = logging.getLogger(__name__)


class S3ObjectStorage(ObjectStorage):
    """Private-bucket S3-compatible storage with tenant-scoped keys."""

    def __init__(self, settings: Settings) -> None:
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "boto3 is required for OBJECT_STORAGE_BACKEND=s3"
            ) from exc

        if not settings.s3_bucket.strip():
            raise ValueError("S3_BUCKET is required for s3 object storage")
        if (
            not settings.s3_access_key_id.strip()
            or not settings.s3_secret_access_key.strip()
        ):
            raise ValueError("S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required")

        self._bucket = settings.s3_bucket.strip()
        self._max_bytes = int(settings.object_storage_max_upload_bytes)
        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": settings.s3_region or "us-east-1",
            "aws_access_key_id": settings.s3_access_key_id,
            "aws_secret_access_key": settings.s3_secret_access_key,
            "config": Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "path"
                    if settings.s3_force_path_style
                    else "auto"
                },
            ),
        }
        if settings.s3_endpoint_url.strip():
            kwargs["endpoint_url"] = settings.s3_endpoint_url.strip()
        self._client = boto3.client(**kwargs)

    def _key(self, tenant_id: UUID, object_key: str) -> str:
        safe = sanitize_object_key(object_key)
        # Never allow caller to escape tenant prefix.
        return f"tenants/{tenant_id}/{safe}"

    def put(
        self,
        *,
        tenant_id: UUID,
        object_key: str,
        data: bytes,
        mime_type: str,
    ) -> StoredObject:
        if len(data) > self._max_bytes:
            raise ValueError("object_too_large")
        mime = validate_object_mime_type(mime_type)
        key = self._key(tenant_id, object_key)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=mime,
            ACL="private",
        )
        return StoredObject(
            object_key=object_key,
            size_bytes=len(data),
            mime_type=mime,
            backend="s3",
        )

    def get(self, *, tenant_id: UUID, object_key: str) -> bytes:
        key = self._key(tenant_id, object_key)
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        body = obj["Body"].read()
        return bytes(body)

    def delete(self, *, tenant_id: UUID, object_key: str) -> None:
        key = self._key(tenant_id, object_key)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, *, tenant_id: UUID, object_key: str) -> bool:
        key = self._key(tenant_id, object_key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def create_download_url(
        self, *, tenant_id: UUID, object_key: str, ttl_seconds: int = 300
    ) -> str:
        key = self._key(tenant_id, object_key)
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=int(ttl_seconds),
            )
        )
