"""Fail-closed tenant resolution via platform API + signed metadata."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class TenantResolveError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TenantResolution:
    tenant_id: str
    phone_number_id: str | None
    e164: str | None
    source: str
    livekit_inbound_trunk_id: str | None = None
    livekit_dispatch_rule_id: str | None = None


def verify_signed_metadata(raw: str | None, secret: str) -> dict[str, Any] | None:
    if not raw or not raw.strip() or not secret:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    provided = data.get("sig")
    if not isinstance(provided, str) or not provided:
        return None
    body = {k: v for k, v in data.items() if k != "sig"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(provided, expected):
        return None
    return body


def sign_metadata(payload: dict[str, Any], secret: str) -> str:
    body = {k: v for k, v in payload.items() if k != "sig"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    body["sig"] = sig
    return json.dumps(body, separators=(",", ":"))


class PlatformTenantResolver:
    """Resolve tenant via platform internal API; fail closed for SIP."""

    def __init__(
        self,
        *,
        platform_base_url: str,
        internal_token: str,
        metadata_hmac_secret: str,
        env_tenant_id: str | None = None,
        allow_env_fallback: bool = True,
        timeout_sec: float = 5.0,
    ) -> None:
        self._base = platform_base_url.rstrip("/")
        self._token = internal_token
        self._secret = metadata_hmac_secret
        self._env_tenant_id = env_tenant_id
        self._allow_env_fallback = allow_env_fallback
        self._timeout = timeout_sec

    def resolve(
        self,
        *,
        job_metadata: str | None,
        called_number: str | None,
        livekit_inbound_trunk_id: str | None,
        is_sip: bool,
    ) -> TenantResolution:
        # Local signed-metadata check first (priority 1) when platform unreachable
        # still prefer calling platform which enforces DID active/verified rules.
        if self._base and self._token:
            try:
                return self._resolve_via_platform(
                    job_metadata=job_metadata,
                    called_number=called_number,
                    livekit_inbound_trunk_id=livekit_inbound_trunk_id,
                    is_sip=is_sip,
                )
            except TenantResolveError:
                raise
            except Exception as exc:
                if is_sip:
                    raise TenantResolveError(
                        "platform_unreachable",
                        f"Tenant resolution failed for SIP call: {exc}",
                    ) from exc
                # Non-SIP may fall through to local metadata / env.

        meta = verify_signed_metadata(job_metadata, self._secret)
        if meta and meta.get("tenant_id"):
            if is_sip and not called_number and not livekit_inbound_trunk_id:
                raise TenantResolveError(
                    "unresolved",
                    "SIP call missing called DID / trunk for fail-closed resolve",
                )
            return TenantResolution(
                tenant_id=str(meta["tenant_id"]),
                phone_number_id=(
                    str(meta["phone_number_id"]) if meta.get("phone_number_id") else None
                ),
                e164=str(meta["did"]) if meta.get("did") else called_number,
                source="signed_metadata_local",
            )

        if not is_sip and self._allow_env_fallback and self._env_tenant_id:
            return TenantResolution(
                tenant_id=self._env_tenant_id,
                phone_number_id=None,
                e164=None,
                source="env_fallback",
            )

        raise TenantResolveError("unresolved", "Unable to resolve tenant")

    def _resolve_via_platform(
        self,
        *,
        job_metadata: str | None,
        called_number: str | None,
        livekit_inbound_trunk_id: str | None,
        is_sip: bool,
    ) -> TenantResolution:
        payload = json.dumps(
            {
                "job_metadata": job_metadata,
                "called_number": called_number,
                "livekit_inbound_trunk_id": livekit_inbound_trunk_id,
                "is_sip": is_sip,
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self._base}/internal/telephony/resolve",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Internal-Token": self._token,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            code = "resolve_denied"
            try:
                detail = json.loads(body).get("detail") or {}
                if isinstance(detail, dict) and detail.get("code"):
                    code = str(detail["code"])
            except json.JSONDecodeError:
                pass
            raise TenantResolveError(code, body) from exc

        return TenantResolution(
            tenant_id=str(data["tenant_id"]),
            phone_number_id=data.get("phone_number_id"),
            e164=data.get("e164"),
            source=str(data.get("source") or "platform"),
            livekit_inbound_trunk_id=data.get("livekit_inbound_trunk_id"),
            livekit_dispatch_rule_id=data.get("livekit_dispatch_rule_id"),
        )

    def notify_inbound_observed(
        self,
        *,
        called_number: str,
        caller_number: str | None,
        livekit_inbound_trunk_id: str | None,
        livekit_room_name: str | None,
        provider_call_id: str | None,
    ) -> dict[str, Any] | None:
        if not self._base or not self._token:
            return None
        payload = json.dumps(
            {
                "called_number": called_number,
                "caller_number": caller_number,
                "livekit_inbound_trunk_id": livekit_inbound_trunk_id,
                "livekit_room_name": livekit_room_name,
                "provider_call_id": provider_call_id,
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self._base}/internal/telephony/inbound-observed",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Internal-Token": self._token,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def resolver_from_env() -> PlatformTenantResolver:
    return PlatformTenantResolver(
        platform_base_url=os.getenv("PLATFORM_API_URL", "").strip(),
        internal_token=os.getenv("INTERNAL_SERVICE_TOKEN", "").strip(),
        metadata_hmac_secret=os.getenv("METADATA_HMAC_SECRET", "").strip(),
        env_tenant_id=os.getenv("TENANT_ID", "").strip() or None,
        allow_env_fallback=os.getenv("ALLOW_ENV_TENANT_FALLBACK", "true").lower()
        in {"1", "true", "yes"},
    )
