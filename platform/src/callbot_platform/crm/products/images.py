"""Product image upload, primary selection, and soft archive."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.serialize import serialize_image
from callbot_platform.db.models import Product, ProductImage, ProductVariant
from callbot_platform.storage import get_object_storage
from callbot_platform.storage.base import validate_product_image_mime_type
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def _sniff_image_mime(data: bytes) -> str | None:
    if len(data) >= 3 and data[0:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 4 and data[0:4] == b"\x89PNG":
        return "image/png"
    if len(data) >= 4 and data[0:4] == b"GIF8":
        return "image/gif"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _trim(value: str | None, *, max_len: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise CrmError(f"invalid_{field}", f"{field} is too long")
    return cleaned


class ProductImageService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._storage = get_object_storage(self._settings)

    def list(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        variant_id: UUID | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self._load_product(tenant_id, product_id, require_active=False)
        if variant_id is not None:
            self._load_variant(tenant_id, product_id, variant_id)
        q = select(ProductImage).where(
            ProductImage.tenant_id == tenant_id,
            ProductImage.product_id == product_id,
        )
        if variant_id is not None:
            q = q.where(ProductImage.variant_id == variant_id)
        if not include_archived:
            q = q.where(ProductImage.archived_at.is_(None))
        q = q.order_by(
            ProductImage.is_primary.desc(),
            ProductImage.sort_order.asc(),
            ProductImage.created_at.asc(),
        ).limit(max(1, min(limit, 200)))
        result: list[dict[str, Any]] = []
        for image in self._session.scalars(q).all():
            url = None
            if image.archived_at is None:
                url = self._storage.create_download_url(
                    tenant_id=tenant_id, object_key=image.object_key
                )
            result.append(serialize_image(image, download_url=url))
        return result

    def get(
        self,
        tenant_id: UUID,
        product_id: UUID,
        image_id: UUID,
        *,
        include_archived: bool = True,
    ) -> dict[str, Any]:
        image = self._load_image(
            tenant_id, product_id, image_id, require_active=not include_archived
        )
        url = None
        if image.archived_at is None:
            url = self._storage.create_download_url(
                tenant_id=tenant_id, object_key=image.object_key
            )
        return serialize_image(image, download_url=url)

    def upload(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        data: bytes,
        content_type: str,
        alt_text: str | None = None,
        variant_id: UUID | None = None,
        is_primary: bool | None = None,
        sort_order: int | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        self._load_product(tenant_id, product_id, require_active=True)
        if variant_id is not None:
            self._load_variant(tenant_id, product_id, variant_id)

        max_bytes = int(self._settings.object_storage_max_upload_bytes)
        if len(data) > max_bytes:
            raise CrmError("object_too_large", "Image exceeds maximum upload size")
        if not data:
            raise CrmError("invalid_image", "Image data is empty")

        try:
            declared = validate_product_image_mime_type(content_type)
        except ValueError as exc:
            raise CrmError(
                "unsupported_image_type", "Unsupported product image type"
            ) from exc

        sniffed = _sniff_image_mime(data)
        if sniffed is None:
            raise CrmError(
                "unsupported_image_type",
                "Image content does not match a supported format",
            )
        if sniffed != declared:
            raise CrmError(
                "unsupported_image_type",
                "Image content type does not match file contents",
            )

        ext = _EXT_BY_MIME[declared]
        object_key = f"products/{product_id}/images/{uuid.uuid4().hex}.{ext}"
        stored = None
        try:
            stored = self._storage.put(
                tenant_id=tenant_id,
                object_key=object_key,
                data=data,
                mime_type=declared,
            )
        except ValueError as exc:
            msg = str(exc)
            if "object_too_large" in msg:
                raise CrmError(
                    "object_too_large", "Image exceeds maximum upload size"
                ) from exc
            if "unsupported" in msg:
                raise CrmError(
                    "unsupported_image_type", "Unsupported product image type"
                ) from exc
            raise CrmError("invalid_image", "Failed to store image") from exc

        make_primary = bool(is_primary) if is_primary is not None else False
        try:
            # Serialize primary flips against concurrent uploads for this product.
            self._lock_product(tenant_id, product_id)
            if make_primary:
                self._clear_primary(tenant_id, product_id, variant_id=variant_id)

            image = ProductImage(
                tenant_id=tenant_id,
                product_id=product_id,
                variant_id=variant_id,
                object_key=stored.object_key,
                content_type=stored.mime_type,
                file_size=stored.size_bytes,
                alt_text=_trim(alt_text, max_len=255, field="alt_text"),
                sort_order=100 if sort_order is None else int(sort_order),
                is_primary=make_primary,
                storage_backend=stored.backend,
            )
            with self._session.begin_nested():
                self._session.add(image)
                self._session.flush()
        except IntegrityError as exc:
            self._best_effort_delete_object(tenant_id, stored.object_key)
            raise CrmError(
                "image_conflict",
                "Could not save image (primary image conflict)",
            ) from exc
        except Exception:
            self._best_effort_delete_object(tenant_id, stored.object_key)
            raise

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_image_uploaded",
            resource_ids={
                "product_id": str(product_id),
                "image_id": str(image.id),
                "variant_id": str(variant_id) if variant_id else None,
            },
        )
        url = self._storage.create_download_url(
            tenant_id=tenant_id, object_key=image.object_key
        )
        return serialize_image(image, download_url=url)

    def set_primary(
        self,
        tenant_id: UUID,
        product_id: UUID,
        image_id: UUID,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        self._lock_product(tenant_id, product_id)
        image = self._load_image(tenant_id, product_id, image_id, require_active=True)
        try:
            with self._session.begin_nested():
                self._clear_primary(tenant_id, product_id, variant_id=image.variant_id)
                image.is_primary = True
                image.updated_at = datetime.now(UTC)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "image_conflict",
                "Could not set primary image",
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_image_set_primary",
            resource_ids={
                "product_id": str(product_id),
                "image_id": str(image_id),
            },
        )
        url = self._storage.create_download_url(
            tenant_id=tenant_id, object_key=image.object_key
        )
        return serialize_image(image, download_url=url)

    def archive(
        self,
        tenant_id: UUID,
        product_id: UUID,
        image_id: UUID,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        image = self._load_image(tenant_id, product_id, image_id, require_active=False)
        if image.archived_at is not None:
            return serialize_image(image)
        # Soft-archive only. Deleting object storage inside the DB transaction
        # can leave a live row pointing at a missing blob if commit fails later.
        image.archived_at = datetime.now(UTC)
        image.is_primary = False
        image.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_image_archived",
            resource_ids={
                "product_id": str(product_id),
                "image_id": str(image_id),
            },
        )
        return serialize_image(image)

    def _lock_product(self, tenant_id: UUID, product_id: UUID) -> Product:
        product = self._session.scalar(
            select(Product)
            .where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if product is None:
            raise CrmError("not_found", "Product not found for tenant")
        return product

    def _best_effort_delete_object(self, tenant_id: UUID, object_key: str) -> None:
        try:
            self._storage.delete(tenant_id=tenant_id, object_key=object_key)
        except Exception:
            logger.exception(
                "product_image_storage_cleanup_failed",
                extra={
                    "tenant_id": str(tenant_id),
                    "object_key": object_key,
                },
            )

    def _clear_primary(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        variant_id: UUID | None,
    ) -> None:
        stmt = (
            update(ProductImage)
            .where(
                ProductImage.tenant_id == tenant_id,
                ProductImage.product_id == product_id,
                ProductImage.archived_at.is_(None),
                ProductImage.is_primary.is_(True),
            )
            .values(is_primary=False, updated_at=datetime.now(UTC))
        )
        if variant_id is None:
            stmt = stmt.where(ProductImage.variant_id.is_(None))
        else:
            stmt = stmt.where(ProductImage.variant_id == variant_id)
        self._session.execute(stmt)

    def _load_product(
        self, tenant_id: UUID, product_id: UUID, *, require_active: bool
    ) -> Product:
        product = self._session.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
            )
        )
        if product is None:
            raise CrmError("not_found", "Product not found for tenant")
        if require_active and product.archived_at is not None:
            raise CrmError("product_archived", "Product is archived")
        return product

    def _load_variant(
        self, tenant_id: UUID, product_id: UUID, variant_id: UUID
    ) -> ProductVariant:
        variant = self._session.scalar(
            select(ProductVariant).where(
                ProductVariant.id == variant_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.product_id == product_id,
                ProductVariant.archived_at.is_(None),
            )
        )
        if variant is None:
            raise CrmError("not_found", "Variant not found for product")
        return variant

    def _load_image(
        self,
        tenant_id: UUID,
        product_id: UUID,
        image_id: UUID,
        *,
        require_active: bool,
    ) -> ProductImage:
        image = self._session.scalar(
            select(ProductImage).where(
                ProductImage.id == image_id,
                ProductImage.tenant_id == tenant_id,
                ProductImage.product_id == product_id,
            )
        )
        if image is None:
            raise CrmError("not_found", "Image not found for product")
        if require_active and image.archived_at is not None:
            raise CrmError("not_found", "Image not found for product")
        return image
