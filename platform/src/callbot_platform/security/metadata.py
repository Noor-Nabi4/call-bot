"""HMAC signing for LiveKit job metadata."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


class MetadataSigner:
    def __init__(self, secret: str) -> None:
        if not secret or not secret.strip():
            raise ValueError("METADATA_HMAC_SECRET is required")
        self._secret = secret.strip().encode("utf-8")

    def sign_payload(self, payload: dict[str, Any]) -> str:
        body = {k: v for k, v in payload.items() if k != "sig"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(
            self._secret, canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        body["sig"] = sig
        return json.dumps(body, separators=(",", ":"))

    def verify_and_parse(self, raw: str | None) -> dict[str, Any] | None:
        if not raw or not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        provided = data.get("sig")
        if not provided or not isinstance(provided, str):
            return None
        body = {k: v for k, v in data.items() if k != "sig"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            self._secret, canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(provided, expected):
            return None
        return body
