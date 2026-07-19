"""Tenant-scoped CRM function tools for the Realtime voice agent.

Docs: https://docs.livekit.io/agents/logic/tools/definition/
"""

from __future__ import annotations

import hashlib
from typing import Any

from livekit.agents import RunContext, function_tool
from livekit.agents.llm import ToolError

from session.userdata import SessionUserData
from tools.platform_crm import PlatformCrmClient, PlatformCrmError


def _userdata(context: RunContext) -> SessionUserData:
    data = context.session.userdata
    if not isinstance(data, SessionUserData):
        raise ToolError(
            "I cannot save that yet because the call is not linked to a business. "
            "Please try again in a moment."
        )
    return data


def _reject_tenant_override(**kwargs: Any) -> None:
    if "tenant_id" in kwargs and kwargs.get("tenant_id") is not None:
        raise ToolError(
            "I cannot change which business this call belongs to. "
            "Please continue with the current request."
        )


def build_crm_tools(client: PlatformCrmClient) -> list[Any]:
    """Build CRM tools closed over the platform client."""

    @function_tool()
    async def get_call_context(context: RunContext) -> dict[str, Any]:
        """Get known call context for this session (caller phone, business name).

        Use this to recall the caller's phone if already known from SIP, or the
        business name. Do not invent missing values.
        """
        data = _userdata(context)
        return {
            "business_name": data.business_name,
            "caller_number": data.caller_number,
            "called_number": data.called_number,
            "is_sip": data.is_sip,
            "customer_id": data.customer_id,
            "has_platform_call": data.platform_call_id is not None,
        }

    @function_tool()
    async def lookup_customer_by_phone(
        context: RunContext,
        phone: str,
    ) -> dict[str, Any]:
        """Look up an existing customer for this business by phone number.

        Args:
            phone: Customer phone in E.164 or a dialable local format.
        """
        _reject_tenant_override()
        data = _userdata(context)
        try:
            result = client.lookup_customer(tenant_id=data.tenant_id, phone=phone)
        except PlatformCrmError as exc:
            raise ToolError(
                "I could not look up that customer right now. Please confirm the "
                "phone number and try again."
            ) from exc
        if result.get("found") and result.get("customer"):
            customer = result["customer"]
            data.customer_id = customer.get("id")
            data.caller_number = phone
            return {"found": True, "customer": customer}
        return {"found": False, "customer": None}

    @function_tool()
    async def create_or_update_customer(
        context: RunContext,
        name: str,
        phone: str,
        caller_confirmed: bool,
        email: str | None = None,
        address: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a customer record after the caller confirms details aloud.

        Args:
            name: Customer full name.
            phone: Callback or caller phone number.
            caller_confirmed: Must be true only after the caller verbally confirmed.
            email: Optional email.
            address: Service address.
        """
        _reject_tenant_override()
        if not caller_confirmed:
            raise ToolError(
                "Please confirm the name, phone, and address with the caller "
                "before saving the customer record."
            )
        data = _userdata(context)
        context.disallow_interruptions()
        try:
            result = client.upsert_customer(
                tenant_id=data.tenant_id,
                name=name,
                phone=phone,
                email=email,
                address=address,
            )
        except PlatformCrmError as exc:
            raise ToolError(
                "I could not save the customer details. Please confirm them and try again."
            ) from exc
        customer = result.get("customer") or {}
        data.customer_id = customer.get("id")
        data.caller_number = phone
        return {"ok": True, "customer": customer}

    @function_tool()
    async def create_lead(
        context: RunContext,
        service_type: str,
        caller_confirmed: bool,
        urgency: str = "normal",
        notes: str | None = None,
        preferred_time_window: str | None = None,
    ) -> dict[str, Any]:
        """Create a service lead / job request after the caller confirms the summary.

        Does not book a calendar slot. Captures preferred time window only.

        Args:
            service_type: Type of service requested (for example AC repair).
            caller_confirmed: Must be true only after verbal confirmation of the summary.
            urgency: One of low, normal, high, emergency.
            notes: Extra notes from the caller.
            preferred_time_window: Preferred day or time window in plain language.
        """
        _reject_tenant_override()
        if not caller_confirmed:
            raise ToolError(
                "Please repeat the summary and get a clear yes from the caller "
                "before creating the job request."
            )
        data = _userdata(context)
        if not data.customer_id:
            raise ToolError(
                "Save the customer with create_or_update_customer before creating a lead."
            )
        digest = hashlib.sha256(
            f"{data.call_id}|{data.customer_id}|{service_type}|{urgency}|{notes or ''}".encode()
        ).hexdigest()[:24]
        idem = f"lead:{data.call_id}:{digest}"
        context.disallow_interruptions()
        try:
            result = client.create_lead(
                tenant_id=data.tenant_id,
                customer_id=data.customer_id,
                service_type=service_type,
                urgency=urgency,
                notes=notes,
                preferred_time_window=preferred_time_window,
                call_id=data.platform_call_id,
                idempotency_key=idem,
            )
        except PlatformCrmError as exc:
            raise ToolError(
                "I could not create the job request. Please try confirming again."
            ) from exc
        lead = result.get("lead") or {}
        return {
            "ok": True,
            "reference_code": lead.get("reference_code"),
            "lead": lead,
        }

    return [
        get_call_context,
        lookup_customer_by_phone,
        create_or_update_customer,
        create_lead,
    ]
