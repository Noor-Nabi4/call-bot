"""Phase 14 typed AI business tools (platform executor-backed).

Docs: https://docs.livekit.io/agents/logic/tools/definition/

Trusted tenant/call identity is never taken from model arguments — it comes
from session userdata + call-scope headers on the platform client.
"""

from __future__ import annotations

from typing import Any

from livekit.agents import RunContext, function_tool
from livekit.agents.llm import ToolError

from session.userdata import SessionUserData
from tools.platform_ai_tools import (
    PlatformAiToolsClient,
    PlatformAiToolsError,
    new_operation_id,
)

_CUSTOMER_SAFE = (
    "I couldn't complete that right now. Would you like me to try again, "
    "or speak with a teammate?"
)

_SAFE_BY_CODE: dict[str, str] = {
    "booking_conflict": (
        "The selected time is no longer available. "
        "Offer other times from check_availability — do not say they are booked."
    ),
    "confirmation_required": (
        "Confirm the details with the caller, then call this tool again "
        "with caller_confirmed=true."
    ),
    "permission_denied": "I can't complete that request.",
    "availability_empty": "I don't see an opening that matches those times.",
    "inventory_unavailable": "That item isn't available right now.",
    "not_found": "I couldn't find that record.",
    "customer_not_found": "I couldn't find that customer on file.",
}


def _userdata(context: RunContext) -> SessionUserData:
    data = context.session.userdata
    if not isinstance(data, SessionUserData):
        raise ToolError(_CUSTOMER_SAFE)
    return data


def _reject_privileged(**kwargs: Any) -> None:
    banned = {
        "tenant_id",
        "tenantId",
        "organization_id",
        "permissions",
        "role",
        "created_by",
        "unit_price",
        "subtotal",
        "tax",
        "total",
        "confirmation_token",
        "confirmationToken",
        "operation_id",
        "operationId",
    }
    for key in banned:
        if key in kwargs and kwargs.get(key) is not None:
            raise ToolError(
                "I can't change those system fields. Let's continue with your request."
            )


def _message_for_error(result: dict[str, Any]) -> str:
    err = result.get("error") or {}
    code = str(err.get("code") or "")
    return _SAFE_BY_CODE.get(code, _CUSTOMER_SAFE)


def _unwrap(result: dict[str, Any], *, data: SessionUserData, tool_name: str) -> dict[str, Any]:
    if result.get("ok") is True:
        data.pending_confirmation_token = None
        data.pending_confirmation_tool = None
        data.pending_operation_id = None
        data.record_tool_result(tool_name, ok=True)
        payload = result.get("data")
        return payload if isinstance(payload, dict) else {"data": payload}

    err = result.get("error") or {}
    code = str(err.get("code") or "")
    if code == "confirmation_required":
        token = result.get("confirmationToken")
        if isinstance(token, str) and token:
            data.pending_confirmation_token = token
            data.pending_confirmation_tool = tool_name
        data.record_tool_result(tool_name, ok=False)
        return {
            "needsConfirmation": True,
            "message": _SAFE_BY_CODE["confirmation_required"],
        }

    data.record_tool_result(tool_name, ok=False)
    raise ToolError(_message_for_error(result))


def build_ai_business_tools(client: PlatformAiToolsClient) -> list[Any]:
    """Build Phase 14 tools closed over the platform AI tools client."""

    def _invoke(
        tool_name: str,
        *,
        data: SessionUserData,
        args: dict[str, Any],
        confirmed: bool = False,
        mutation: bool = False,
    ) -> dict[str, Any]:
        op_id: str | None = None
        token: str | None = None
        if mutation:
            if (
                data.pending_operation_id
                and data.pending_confirmation_tool == tool_name
            ):
                op_id = data.pending_operation_id
            else:
                op_id = new_operation_id()
                data.pending_operation_id = op_id
            if confirmed:
                if (
                    data.pending_confirmation_tool != tool_name
                    or not data.pending_confirmation_token
                ):
                    # Force prepare step first — model cannot skip with confirmed=true alone.
                    confirmed = False
                else:
                    token = data.pending_confirmation_token
        try:
            raw = client.invoke(
                tool_name,
                args=args,
                confirmed=confirmed,
                confirmation_token=token,
                operation_id=op_id,
                customer_id=data.customer_id,
                caller_phone=data.caller_number,
                tenant_id=data.tenant_id,
                mutation=mutation,
            )
            return _unwrap(raw, data=data, tool_name=tool_name)
        except PlatformAiToolsError as exc:
            data.record_tool_result(tool_name, ok=False)
            raise ToolError(_CUSTOMER_SAFE) from exc

    @function_tool()
    async def find_customer(
        context: RunContext,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Identify an existing customer. Prefer the known caller phone from the call.

        Args:
            phone: Optional phone; omit to use the trusted caller number from the call.
            email: Optional email if phone is unavailable.
        """
        _reject_privileged()
        data = _userdata(context)
        result = _invoke(
            "find_customer",
            data=data,
            args={"phone": phone, "email": email},
        )
        customer = result.get("customer")
        if result.get("match") == "EXACT" and isinstance(customer, dict):
            data.customer_id = customer.get("id")
        return result

    @function_tool()
    async def create_customer(
        context: RunContext,
        first_name: str,
        phone: str,
        caller_confirmed: bool,
        last_name: str | None = None,
        email: str | None = None,
        address_line1: str | None = None,
        address_city: str | None = None,
        address_region: str | None = None,
        address_postal_code: str | None = None,
    ) -> dict[str, Any]:
        """Create a customer after the caller verbally confirms their details.

        Args:
            first_name: Customer first name.
            phone: Customer phone (E.164 preferred).
            caller_confirmed: Must be true only after verbal confirmation.
            last_name: Optional last name.
            email: Optional email.
            address_line1: Optional street address.
            address_city: Optional city.
            address_region: Optional state/region.
            address_postal_code: Optional postal code.
        """
        _reject_privileged()
        data = _userdata(context)
        address = None
        if address_line1:
            address = {
                "line1": address_line1,
                "city": address_city,
                "region": address_region,
                "postalCode": address_postal_code,
            }
        result = _invoke(
            "create_customer",
            data=data,
            args={
                "firstName": first_name,
                "lastName": last_name,
                "phone": phone,
                "email": email,
                "address": address,
            },
            confirmed=caller_confirmed,
            mutation=True,
        )
        customer = result.get("customer")
        if isinstance(customer, dict) and customer.get("id"):
            data.customer_id = customer["id"]
        return result

    @function_tool()
    async def get_customer_context(
        context: RunContext,
        customer_id: str,
    ) -> dict[str, Any]:
        """Load bounded CRM context for an identified customer.

        Args:
            customer_id: Customer UUID from find_customer or create_customer.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "get_customer_context",
            data=data,
            args={"customerId": customer_id},
        )

    @function_tool()
    async def search_services(
        context: RunContext,
        query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search the service catalog for what the caller needs.

        Args:
            query: Natural-language service request.
            limit: Max results (1-10).
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "search_services",
            data=data,
            args={"query": query, "limit": min(max(limit, 1), 10)},
        )

    @function_tool()
    async def get_service_price(
        context: RunContext,
        service_id: str,
    ) -> dict[str, Any]:
        """Resolve authoritative service pricing from the pricebook.

        Args:
            service_id: Service UUID from search_services.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "get_service_price",
            data=data,
            args={"serviceId": service_id},
        )

    @function_tool()
    async def check_availability(
        context: RunContext,
        service_id: str,
        preferred_date: str | None = None,
        preferred_start_date: str | None = None,
        preferred_end_date: str | None = None,
        location_id: str | None = None,
        emergency: bool = False,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Find advisory appointment slots. Always re-book with create_booking.

        Args:
            service_id: Service UUID.
            preferred_date: YYYY-MM-DD single day preference.
            preferred_start_date: YYYY-MM-DD range start.
            preferred_end_date: YYYY-MM-DD range end.
            location_id: Optional customer location UUID.
            emergency: Use emergency hours when true.
            limit: Max slots (1-10).
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "check_availability",
            data=data,
            args={
                "serviceId": service_id,
                "preferredDate": preferred_date,
                "preferredStartDate": preferred_start_date,
                "preferredEndDate": preferred_end_date,
                "locationId": location_id,
                "emergency": emergency,
                "limit": min(max(limit, 1), 10),
            },
        )

    @function_tool()
    async def create_booking(
        context: RunContext,
        customer_id: str,
        service_id: str,
        starts_at: str,
        ends_at: str,
        timezone: str,
        caller_confirmed: bool,
        location_id: str | None = None,
        technician_id: str | None = None,
        description: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create job + appointment atomically after the caller confirms the slot.

        Args:
            customer_id: Customer UUID.
            service_id: Service UUID.
            starts_at: Slot start (ISO-8601).
            ends_at: Slot end (ISO-8601).
            timezone: IANA timezone for the booking.
            caller_confirmed: Must be true only after verbal confirmation.
            location_id: Optional location UUID.
            technician_id: Optional technician from check_availability.
            description: Job description.
            notes: Optional notes.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "create_booking",
            data=data,
            args={
                "customerId": customer_id,
                "serviceId": service_id,
                "startsAt": starts_at,
                "endsAt": ends_at,
                "timezone": timezone,
                "locationId": location_id,
                "technicianId": technician_id,
                "description": description,
                "notes": notes,
            },
            confirmed=caller_confirmed,
            mutation=True,
        )

    @function_tool()
    async def search_products(
        context: RunContext,
        query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search products for commerce questions.

        Args:
            query: Product search text.
            limit: Max results (1-10).
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "search_products",
            data=data,
            args={"query": query, "limit": min(max(limit, 1), 10)},
        )

    @function_tool()
    async def check_inventory(
        context: RunContext,
        variant_id: str,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Check inventory for a product variant.

        Args:
            variant_id: Variant UUID.
            location_id: Optional inventory location UUID.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "check_inventory",
            data=data,
            args={"variantId": variant_id, "locationId": location_id},
        )

    @function_tool()
    async def get_product_price(
        context: RunContext,
        variant_id: str,
    ) -> dict[str, Any]:
        """Resolve product variant unit price from the catalog.

        Args:
            variant_id: Variant UUID.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "get_product_price",
            data=data,
            args={"variantId": variant_id},
        )

    @function_tool()
    async def create_order(
        context: RunContext,
        customer_id: str,
        variant_id: str,
        quantity: int,
        caller_confirmed: bool,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create an order after the caller confirms items and totals verbally.

        Args:
            customer_id: Customer UUID.
            variant_id: Variant UUID to order.
            quantity: Quantity (>= 1).
            caller_confirmed: Must be true only after verbal confirmation.
            notes: Optional order notes.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "create_order",
            data=data,
            args={
                "customerId": customer_id,
                "items": [{"variantId": variant_id, "quantity": quantity}],
                "notes": notes,
            },
            confirmed=caller_confirmed,
            mutation=True,
        )

    @function_tool()
    async def find_orders(
        context: RunContext,
        customer_id: str | None = None,
        order_number: str | None = None,
    ) -> dict[str, Any]:
        """Find recent orders for a customer or by order number.

        Args:
            customer_id: Optional customer UUID (defaults to identified caller).
            order_number: Optional order number search.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "find_orders",
            data=data,
            args={"customerId": customer_id, "orderNumber": order_number},
        )

    @function_tool()
    async def get_order_status(
        context: RunContext,
        order_id: str | None = None,
        order_number: str | None = None,
    ) -> dict[str, Any]:
        """Get status for one order by id or number.

        Args:
            order_id: Order UUID.
            order_number: Order number.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "get_order_status",
            data=data,
            args={"orderId": order_id, "orderNumber": order_number},
        )

    @function_tool()
    async def find_estimates(
        context: RunContext,
        customer_id: str | None = None,
        estimate_number: str | None = None,
    ) -> dict[str, Any]:
        """Find estimates for a customer or by estimate number.

        Args:
            customer_id: Optional customer UUID.
            estimate_number: Optional estimate number.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "find_estimates",
            data=data,
            args={"customerId": customer_id, "estimateNumber": estimate_number},
        )

    @function_tool()
    async def get_estimate(
        context: RunContext,
        estimate_id: str,
    ) -> dict[str, Any]:
        """Load a single estimate with line items.

        Args:
            estimate_id: Estimate UUID.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "get_estimate",
            data=data,
            args={"estimateId": estimate_id},
        )

    @function_tool()
    async def send_sms(
        context: RunContext,
        customer_id: str,
        message: str,
        purpose: str,
        caller_confirmed: bool,
    ) -> dict[str, Any]:
        """Queue an SMS to the customer's verified phone (not an arbitrary number).

        Args:
            customer_id: Customer UUID.
            message: SMS body.
            purpose: APPOINTMENT_CONFIRMATION | APPOINTMENT_UPDATE | ORDER_UPDATE | GENERAL.
            caller_confirmed: Required confirmation for outbound SMS.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "send_sms",
            data=data,
            args={
                "customerId": customer_id,
                "message": message,
                "purpose": purpose,
            },
            confirmed=caller_confirmed,
            mutation=True,
        )

    @function_tool()
    async def update_customer(
        context: RunContext,
        customer_id: str,
        caller_confirmed: bool,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Update controlled customer fields after verbal confirmation.

        Args:
            customer_id: Customer UUID.
            caller_confirmed: Must be true only after verbal confirmation.
            first_name: Optional new first name.
            last_name: Optional new last name.
            email: Optional new email.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "update_customer",
            data=data,
            args={
                "customerId": customer_id,
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
            },
            confirmed=caller_confirmed,
            mutation=True,
        )

    @function_tool()
    async def reschedule_appointment(
        context: RunContext,
        appointment_id: str,
        starts_at: str,
        ends_at: str,
        timezone: str,
        caller_confirmed: bool,
    ) -> dict[str, Any]:
        """Reschedule an appointment; slot is revalidated server-side.

        Args:
            appointment_id: Appointment UUID.
            starts_at: New start (ISO-8601).
            ends_at: New end (ISO-8601).
            timezone: IANA timezone.
            caller_confirmed: Must be true only after verbal confirmation.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "reschedule_appointment",
            data=data,
            args={
                "appointmentId": appointment_id,
                "startsAt": starts_at,
                "endsAt": ends_at,
                "timezone": timezone,
            },
            confirmed=caller_confirmed,
            mutation=True,
        )

    @function_tool()
    async def cancel_appointment(
        context: RunContext,
        appointment_id: str,
        caller_confirmed: bool,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Cancel an appointment after the caller confirms.

        Args:
            appointment_id: Appointment UUID.
            caller_confirmed: Must be true only after verbal confirmation.
            reason: Optional cancellation reason.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "cancel_appointment",
            data=data,
            args={"appointmentId": appointment_id, "reason": reason},
            confirmed=caller_confirmed,
            mutation=True,
        )

    @function_tool()
    async def request_human(
        context: RunContext,
        reason: str,
        summary: str,
    ) -> dict[str, Any]:
        """Request a human handoff. Do not manipulate SIP/LiveKit transfer internals.

        Args:
            reason: CUSTOMER_REQUEST | COMPLAINT | AUTHORIZATION_LIMIT | SYSTEM_FAILURE | UNSUPPORTED_REQUEST | IDENTITY_AMBIGUITY | OTHER.
            summary: Short summary for the human agent.
        """
        _reject_privileged()
        data = _userdata(context)
        return _invoke(
            "request_human",
            data=data,
            args={"reason": reason, "summary": summary},
            mutation=True,
        )

    return [
        find_customer,
        create_customer,
        update_customer,
        get_customer_context,
        search_services,
        get_service_price,
        check_availability,
        create_booking,
        reschedule_appointment,
        cancel_appointment,
        search_products,
        check_inventory,
        get_product_price,
        create_order,
        find_orders,
        get_order_status,
        find_estimates,
        get_estimate,
        send_sms,
        request_human,
    ]
