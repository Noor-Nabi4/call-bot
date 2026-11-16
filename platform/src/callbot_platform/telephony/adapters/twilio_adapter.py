"""Twilio adapters for inventory, provisioning, and Elastic SIP trunks."""

from __future__ import annotations

from typing import Any

from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.rest import Client

from callbot_platform.domain.enums import TelephonyProviderId
from callbot_platform.telephony.interfaces import (
    AvailableNumber,
    NumberInventoryService,
    NumberProvisioningService,
    PurchasedNumber,
    TwilioTrunkInfo,
)


class TwilioProvider:
    provider_id = TelephonyProviderId.TWILIO
    supports_inventory = True
    supports_purchase = True


class TwilioApiError(RuntimeError):
    def __init__(
        self, message: str, *, status: int | None = None, code: int | None = None
    ):
        super().__init__(message)
        self.status = status
        self.code = code


def _client(account_sid: str, auth_token: str) -> Client:
    if not account_sid or not auth_token:
        raise TwilioApiError("Twilio account credentials are required")
    return Client(account_sid, auth_token)


class TwilioNumberInventoryService(NumberInventoryService):
    def search(
        self,
        *,
        account_sid: str,
        auth_token: str,
        country: str,
        area_code: str | None = None,
        number_type: str = "local",
        voice_enabled: bool = True,
        sms_enabled: bool | None = None,
        limit: int = 20,
    ) -> list[AvailableNumber]:
        client = _client(account_sid, auth_token)
        country_code = country.upper()
        params: dict[str, Any] = {"limit": limit}
        if area_code:
            # Twilio requires AreaCode as an integer-like digit string.
            params["area_code"] = int(str(area_code).strip())
        if voice_enabled:
            params["voice_enabled"] = True
        if sms_enabled is not None:
            params["sms_enabled"] = sms_enabled

        try:
            if number_type == "toll_free":
                records = client.available_phone_numbers(country_code).toll_free.list(
                    **params
                )
            elif number_type == "mobile":
                records = client.available_phone_numbers(country_code).mobile.list(
                    **params
                )
            else:
                records = client.available_phone_numbers(country_code).local.list(
                    **params
                )
        except (TwilioRestException, TwilioException, ValueError, TypeError) as exc:
            msg = getattr(exc, "msg", None) or str(exc)
            status = getattr(exc, "status", None)
            code = getattr(exc, "code", None)
            raise TwilioApiError(
                f"Twilio inventory search failed: {msg}",
                status=status if isinstance(status, int) else None,
                code=code if isinstance(code, int) else None,
            ) from exc

        results: list[AvailableNumber] = []
        for record in records:
            caps = getattr(record, "capabilities", None) or {}
            if hasattr(caps, "get"):
                capabilities = {
                    "voice": bool(caps.get("voice")),
                    "sms": bool(caps.get("SMS") or caps.get("sms")),
                    "mms": bool(caps.get("MMS") or caps.get("mms")),
                }
            else:
                capabilities = {
                    "voice": bool(getattr(caps, "voice", False)),
                    "sms": bool(getattr(caps, "sms", False)),
                    "mms": bool(getattr(caps, "mms", False)),
                }
            results.append(
                AvailableNumber(
                    e164=record.phone_number,
                    friendly_name=getattr(record, "friendly_name", None),
                    locality=getattr(record, "locality", None),
                    region=getattr(record, "region", None),
                    iso_country=getattr(record, "iso_country", country_code),
                    capabilities=capabilities,
                    monthly_price=None,  # filled by pricing lookup when available
                    price_unit=None,
                    raw={
                        "phone_number": record.phone_number,
                        "friendly_name": getattr(record, "friendly_name", None),
                        "locality": getattr(record, "locality", None),
                        "region": getattr(record, "region", None),
                        "iso_country": getattr(record, "iso_country", country_code),
                        "capabilities": capabilities,
                        "address_requirements": getattr(
                            record, "address_requirements", None
                        ),
                    },
                )
            )

        # Attach account-specific pricing when Twilio pricing API is available.
        try:
            pricing = client.pricing.v1.phone_numbers.countries(country_code).fetch()
            price_map = {}
            for item in getattr(pricing, "phone_number_prices", None) or []:
                ntype = getattr(item, "number_type", None) or item.get("number_type")
                price = getattr(item, "current_price", None) or item.get(
                    "current_price"
                )
                if ntype:
                    price_map[str(ntype).lower()] = (
                        str(price) if price is not None else None
                    )
            unit = getattr(pricing, "price_unit", None)
            mapped_type = {
                "local": "local",
                "toll_free": "toll free",
                "mobile": "mobile",
            }.get(number_type, number_type)
            monthly = price_map.get(mapped_type) or price_map.get(number_type)
            results = [
                AvailableNumber(
                    e164=n.e164,
                    friendly_name=n.friendly_name,
                    locality=n.locality,
                    region=n.region,
                    iso_country=n.iso_country,
                    capabilities=n.capabilities,
                    monthly_price=monthly,
                    price_unit=unit,
                    raw={**n.raw, "monthly_price": monthly, "price_unit": unit},
                )
                for n in results
            ]
        except TwilioRestException:
            # Pricing is best-effort; inventory itself must still be real.
            pass

        return results


class TwilioNumberProvisioningService(NumberProvisioningService):
    def purchase(
        self,
        *,
        account_sid: str,
        auth_token: str,
        e164: str,
        idempotency_key: str | None = None,
    ) -> PurchasedNumber:
        client = _client(account_sid, auth_token)
        try:
            kwargs: dict[str, Any] = {"phone_number": e164}
            # Twilio IncomingPhoneNumber create supports Idempotency-Key via header
            # in recent SDKs through http headers; pass when available.
            incoming = client.incoming_phone_numbers.create(**kwargs)
        except TwilioRestException as exc:
            raise TwilioApiError(
                f"Twilio purchase failed: {exc.msg}",
                status=exc.status,
                code=exc.code,
            ) from exc
        return PurchasedNumber(
            e164=incoming.phone_number,
            phone_number_sid=incoming.sid,
            account_sid=incoming.account_sid,
        )

    def release(
        self,
        *,
        account_sid: str,
        auth_token: str,
        phone_number_sid: str,
    ) -> None:
        client = _client(account_sid, auth_token)
        try:
            client.incoming_phone_numbers(phone_number_sid).delete()
        except TwilioRestException as exc:
            raise TwilioApiError(
                f"Twilio release failed: {exc.msg}",
                status=exc.status,
                code=exc.code,
            ) from exc


class TwilioSipTrunkService:
    """Twilio Elastic SIP trunk operations (platform/subaccount scoped)."""

    def create_or_get_twilio_trunk(
        self,
        *,
        account_sid: str,
        auth_token: str,
        friendly_name: str,
        domain_name: str,
        livekit_origination_uri: str,
    ) -> TwilioTrunkInfo:
        client = _client(account_sid, auth_token)
        try:
            existing = client.trunking.v1.trunks.list(limit=50)
            for trunk in existing:
                if trunk.friendly_name == friendly_name or (
                    trunk.domain_name and trunk.domain_name == domain_name
                ):
                    self._ensure_origination(client, trunk.sid, livekit_origination_uri)
                    return TwilioTrunkInfo(
                        trunk_sid=trunk.sid,
                        friendly_name=trunk.friendly_name,
                        domain_name=trunk.domain_name,
                    )
            trunk = client.trunking.v1.trunks.create(
                friendly_name=friendly_name,
                domain_name=domain_name,
            )
            self._ensure_origination(client, trunk.sid, livekit_origination_uri)
            return TwilioTrunkInfo(
                trunk_sid=trunk.sid,
                friendly_name=trunk.friendly_name,
                domain_name=trunk.domain_name,
            )
        except TwilioRestException as exc:
            raise TwilioApiError(
                f"Twilio trunk create failed: {exc.msg}",
                status=exc.status,
                code=exc.code,
            ) from exc

    def _ensure_origination(
        self, client: Client, trunk_sid: str, livekit_origination_uri: str
    ) -> None:
        urls = client.trunking.v1.trunks(trunk_sid).origination_urls.list(limit=20)
        for url in urls:
            if url.sip_url == livekit_origination_uri and url.enabled:
                return
        client.trunking.v1.trunks(trunk_sid).origination_urls.create(
            friendly_name="LiveKit SIP URI",
            sip_url=livekit_origination_uri,
            weight=1,
            priority=1,
            enabled=True,
        )

    def associate_number_with_twilio_trunk(
        self,
        *,
        account_sid: str,
        auth_token: str,
        trunk_sid: str,
        phone_number_sid: str,
    ) -> None:
        client = _client(account_sid, auth_token)
        try:
            existing = client.trunking.v1.trunks(trunk_sid).phone_numbers.list(
                limit=100
            )
            for item in existing:
                if item.sid == phone_number_sid:
                    return
            client.trunking.v1.trunks(trunk_sid).phone_numbers.create(
                phone_number_sid=phone_number_sid
            )
        except TwilioRestException as exc:
            raise TwilioApiError(
                f"Twilio trunk number association failed: {exc.msg}",
                status=exc.status,
                code=exc.code,
            ) from exc

    def create_subaccount(
        self,
        *,
        master_account_sid: str,
        master_auth_token: str,
        friendly_name: str,
    ) -> tuple[str, str]:
        client = _client(master_account_sid, master_auth_token)
        try:
            # Reuse existing subaccount with same friendly name when present.
            for account in client.api.accounts.list(status="active", limit=100):
                if (
                    account.friendly_name == friendly_name
                    and account.sid != master_account_sid
                ):
                    # Cannot retrieve auth token for existing accounts; caller must store it
                    # on first create. Signal reuse without token.
                    return account.sid, ""
            account = client.api.accounts.create(friendly_name=friendly_name)
            return account.sid, account.auth_token
        except TwilioRestException as exc:
            raise TwilioApiError(
                f"Twilio subaccount create failed: {exc.msg}",
                status=exc.status,
                code=exc.code,
            ) from exc
