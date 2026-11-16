"""Product catalog serialization."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.products.normalize import money_to_str
from callbot_platform.db.models import (
    Product,
    ProductAttribute,
    ProductBrand,
    ProductCategory,
    ProductImage,
    ProductVariant,
)


def effective_price(
    product: Product, variant: ProductVariant | None = None
) -> str | None:
    if variant is not None and variant.price is not None:
        return money_to_str(variant.price)
    return money_to_str(product.price)


def effective_cost(
    product: Product, variant: ProductVariant | None = None
) -> str | None:
    if variant is not None and variant.cost is not None:
        return money_to_str(variant.cost)
    return money_to_str(product.cost)


def serialize_brand(brand: ProductBrand) -> dict[str, Any]:
    return {
        "id": str(brand.id),
        "name": brand.name,
        "archived_at": brand.archived_at.isoformat() if brand.archived_at else None,
    }


def serialize_category(
    cat: ProductCategory, *, product_count: int | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(cat.id),
        "name": cat.name,
        "slug": cat.slug,
        "description": cat.description,
        "parent_id": str(cat.parent_id) if cat.parent_id else None,
        "status": cat.status,
        "sort_order": cat.sort_order,
        "archived_at": cat.archived_at.isoformat() if cat.archived_at else None,
        "created_at": cat.created_at.isoformat() if cat.created_at else None,
        "updated_at": cat.updated_at.isoformat() if cat.updated_at else None,
    }
    if product_count is not None:
        payload["product_count"] = product_count
    return payload


def serialize_attribute(attr: ProductAttribute) -> dict[str, Any]:
    return {
        "id": str(attr.id),
        "name": attr.name,
        "sort_order": attr.sort_order,
        "values": [
            {
                "id": str(v.id),
                "value": v.value,
                "sort_order": v.sort_order,
            }
            for v in sorted(attr.values or [], key=lambda x: (x.sort_order, x.value))
        ],
    }


def serialize_variant(
    variant: ProductVariant,
    *,
    product: Product | None = None,
    include_cost: bool = False,
) -> dict[str, Any]:
    attrs = []
    for link in variant.attribute_links or []:
        val = link.attribute_value
        if val is None:
            continue
        attr = val.attribute
        attrs.append(
            {
                "attribute_id": str(attr.id) if attr else None,
                "attribute_name": attr.name if attr else None,
                "value_id": str(val.id),
                "value": val.value,
            }
        )
    payload: dict[str, Any] = {
        "id": str(variant.id),
        "product_id": str(variant.product_id),
        "sku": variant.sku,
        "name": variant.name,
        "price": money_to_str(variant.price),
        "effective_price": effective_price(product, variant)
        if product is not None
        else money_to_str(variant.price),
        "status": variant.status,
        "stock_on_hand": variant.stock_on_hand,
        "inventory_item_id": str(variant.inventory_item_id)
        if variant.inventory_item_id
        else None,
        "attributes": attrs,
        "archived_at": variant.archived_at.isoformat() if variant.archived_at else None,
        "created_at": variant.created_at.isoformat() if variant.created_at else None,
        "updated_at": variant.updated_at.isoformat() if variant.updated_at else None,
    }
    if include_cost:
        payload["cost"] = money_to_str(variant.cost)
        payload["effective_cost"] = (
            effective_cost(product, variant)
            if product is not None
            else money_to_str(variant.cost)
        )
    return payload


def serialize_image(
    image: ProductImage, *, download_url: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(image.id),
        "product_id": str(image.product_id),
        "variant_id": str(image.variant_id) if image.variant_id else None,
        "content_type": image.content_type,
        "file_size": image.file_size,
        "width": image.width,
        "height": image.height,
        "alt_text": image.alt_text,
        "sort_order": image.sort_order,
        "is_primary": bool(image.is_primary),
        "archived_at": image.archived_at.isoformat() if image.archived_at else None,
        "created_at": image.created_at.isoformat() if image.created_at else None,
    }
    if download_url is not None:
        payload["download_url"] = download_url
    return payload


def serialize_product(
    product: Product,
    *,
    include_cost: bool = False,
    include_variants: bool = False,
    include_attributes: bool = False,
    include_images: bool = False,
    image_urls: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(product.id),
        "name": product.name,
        "sku": product.sku,
        "description": product.description,
        "category_id": str(product.category_id) if product.category_id else None,
        "category": serialize_category(product.category)
        if product.category is not None
        else None,
        "brand_id": str(product.brand_id) if product.brand_id else None,
        "brand": serialize_brand(product.brand) if product.brand is not None else None,
        "price": money_to_str(product.price),
        "tax_rate": money_to_str(product.tax_rate),
        "weight": money_to_str(product.weight),
        "weight_unit": product.weight_unit,
        "status": product.status,
        "archived_at": product.archived_at.isoformat() if product.archived_at else None,
        "created_by": product.created_by,
        "updated_by": product.updated_by,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "has_variants": any(v.archived_at is None for v in (product.variants or [])),
    }
    if include_cost:
        payload["cost"] = money_to_str(product.cost)
    if include_variants:
        payload["variants"] = [
            serialize_variant(v, product=product, include_cost=include_cost)
            for v in (product.variants or [])
            if v.archived_at is None
        ]
    if include_attributes:
        payload["attributes"] = [
            serialize_attribute(a)
            for a in sorted(
                product.attributes or [], key=lambda x: (x.sort_order, x.name)
            )
        ]
    if include_images:
        urls = image_urls or {}
        payload["images"] = [
            serialize_image(img, download_url=urls.get(str(img.id)))
            for img in sorted(
                [i for i in (product.images or []) if i.archived_at is None],
                key=lambda x: (not x.is_primary, x.sort_order, str(x.id)),
            )
        ]
    return payload
