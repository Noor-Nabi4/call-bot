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


def sanitize_object_key(object_key: str) -> str:
    """Normalize a caller-supplied object key; reject traversal / absolute paths.

    Storage backends must still prefix with ``tenants/{tenant_id}/`` (or equivalent).
    Prefer opaque IDs over user filenames when possible.
    """
    raw = object_key or ""
    if "\x00" in raw:
        raise ValueError("invalid_object_key")
    # Reject URL-encoded traversal before any decode side effects in proxies.
    lowered = raw.lower()
    if "%2e%2e" in lowered or "%2e." in lowered or ".%2e" in lowered:
        raise ValueError("invalid_object_key")
    # Absolute / drive-letter paths are never valid object keys.
    if raw.startswith(("/", "\\")) or (len(raw) >= 2 and raw[1] == ":"):
        raise ValueError("invalid_object_key")
    normalized = raw.replace("\\", "/").lstrip("/")
    if not normalized or normalized.startswith("/") or ":" in normalized.split("/")[0]:
        raise ValueError("invalid_object_key")
    parts: list[str] = []
    for part in normalized.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("invalid_object_key")
        parts.append(part)
    if not parts:
        raise ValueError("invalid_object_key")
    return "/".join(parts)


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
