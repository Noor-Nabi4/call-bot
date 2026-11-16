"""Bounded, filter-safe knowledge metadata."""

from __future__ import annotations

import json
from typing import Any

from callbot_platform.knowledge.constants import (
    ALLOWED_METADATA_KEYS,
    MAX_METADATA_JSON_BYTES,
    MAX_METADATA_KEY_LEN,
    MAX_METADATA_TAGS,
    MAX_METADATA_VALUE_LEN,
)
from callbot_platform.knowledge.repos import KnowledgeError


def normalize_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise KnowledgeError("invalid_metadata", "metadata must be an object")
    out: dict[str, Any] = {}
    for key, value in raw.items():
        k = str(key).strip()[:MAX_METADATA_KEY_LEN]
        if k not in ALLOWED_METADATA_KEYS:
            raise KnowledgeError(
                "invalid_metadata",
                f"metadata key not allowed: {k}",
            )
        if k == "tags":
            if not isinstance(value, list):
                raise KnowledgeError("invalid_metadata", "tags must be a list")
            tags = [str(t).strip()[:MAX_METADATA_VALUE_LEN] for t in value if str(t).strip()]
            out["tags"] = tags[:MAX_METADATA_TAGS]
            continue
        if value is None:
            continue
        s = str(value).strip()[:MAX_METADATA_VALUE_LEN]
        if s:
            out[k] = s
    encoded = json.dumps(out, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_METADATA_JSON_BYTES:
        raise KnowledgeError("invalid_metadata", "metadata too large")
    return out
