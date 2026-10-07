"""Object storage interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

ALLOWED_OBJECT_MIME_TYPES: frozenset[str] = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/webm",
        "application/octet-stream",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "text/html",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
)

ALLOWED_PRODUCT_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
)


def validate_object_mime_type(mime_type: str) -> str:
    cleaned = (mime_type or "").strip().lower() or "application/octet-stream"
    if cleaned not in ALLOWED_OBJECT_MIME_TYPES:
        raise ValueError(f"unsupported_content_type:{cleaned}")
    return cleaned


def validate_product_image_mime_type(mime_type: str) -> str:
    cleaned = (mime_type or "").strip().lower()
    if cleaned not in ALLOWED_PRODUCT_IMAGE_MIME_TYPES:
        raise ValueError(f"unsupported_image_type:{cleaned}")
    return cleaned


@dataclass(frozen=True, slots=True)
class StoredObject:
    object_key: str
    size_bytes: int
    mime_type: str
    backend: str


class ObjectStorage(ABC):
    @abstractmethod
    def put(
        self,
        *,
        tenant_id: UUID,
        object_key: str,
        data: bytes,
        mime_type: str,
    ) -> StoredObject: ...

    @abstractmethod
    def get(self, *, tenant_id: UUID, object_key: str) -> bytes: ...

    @abstractmethod
    def delete(self, *, tenant_id: UUID, object_key: str) -> None: ...

    @abstractmethod
    def create_download_url(
        self, *, tenant_id: UUID, object_key: str, ttl_seconds: int = 300
    ) -> str: ...

    def exists(self, *, tenant_id: UUID, object_key: str) -> bool:
        try:
            self.get(tenant_id=tenant_id, object_key=object_key)
            return True
        except Exception:
            return False
