"""Tenant-scoped scheduling function tools for the Realtime voice agent."""

from __future__ import annotations

import hashlib
from typing import Any

from livekit.agents import RunContext, function_tool
from livekit.agents.llm import ToolError

from session.userdata import SessionUserData
from tools.platform_scheduling import PlatformSchedulingClient, PlatformSchedulingError


def _userdata(context: RunContext) -> SessionUserData:
    data = context.session.userdata
    if not isinstance(data, SessionUserData):
        raise ToolError(
            "I cannot book that yet because the call is not linked to a business. "
            "Please try again in a moment."
        )
    return data


def _reject_tenant_override(**kwargs: Any) -> None:
    if "tenant_id" in kwargs and kwargs.get("tenant_id") is not None:
        raise ToolError(
            "I cannot change which business this call belongs to. "
            "Please continue with the current request."
        )


def build_scheduling_tools(client: PlatformSchedulingClient) -> list[Any]:
    """Build scheduling tools closed over the platform client."""

    @function_tool()
    async def get_available_slots(
        context: RunContext,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch real available appointment slots for this business.

        Use this before offering times. Do not invent availability.

        Args:
            from_date: Optional local start date YYYY-MM-DD.
            to_date: Optional local end date YYYY-MM-DD.
        """
        _reject_tenant_override()
        data = _userdata(context)
        try:
            result = client.list_slots(
                tenant_id=data.tenant_id,
                from_date=from_date,
                to_date=to_date,
                limit=12,
            )
        except PlatformSchedulingError as exc:
            raise ToolError(
                "I could not look up available times right now. "
                "Please try again in a moment."
            ) from exc
        slots = result.get("slots") or []
        # Keep responses short for voice: first few slots.
        return {
            "timezone": result.get("timezone"),
            "slot_minutes": result.get("slot_minutes"),
            "slots": slots[:6],
            "count": len(slots),
        }

    @function_tool()
    async def book_appointment(
        context: RunContext,
        starts_at: str,
        service_type: str,
        caller_confirmed: bool,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Book an appointment after the caller confirms the exact time aloud.

        Args:
            starts_at: Slot start time from get_available_slots (ISO UTC or local).
            service_type: Service being booked (for example AC repair).
            caller_confirmed: Must be true only after verbal confirmation.
            notes: Optional notes from the caller.
        """
        _reject_tenant_override()
        if not caller_confirmed:
            raise ToolError(
                "Please confirm the appointment day and time with the caller "
                "before booking."
            )
        data = _userdata(context)
        if not data.customer_id:
            raise ToolError(
                "Save the customer with create_or_update_customer before booking."
            )
        digest = hashlib.sha256(
            f"{data.call_id}|{data.customer_id}|{starts_at}|{service_type}".encode()
        ).hexdigest()[:24]
        idem = f"appt:{data.call_id}:{digest}"
        context.disallow_interruptions()
        try:
            result = client.book_appointment(
                tenant_id=data.tenant_id,
                customer_id=data.customer_id,
                starts_at=starts_at,
                service_type=service_type,
                notes=notes,
                call_id=data.platform_call_id,
                idempotency_key=idem,
            )
        except PlatformSchedulingError as exc:
            if exc.code == "slot_unavailable":
                raise ToolError(
                    "That time was just taken. Please offer another available slot."
                ) from exc
            raise ToolError(
                "I could not book that appointment. Please confirm the time and try again."
            ) from exc
        appointment = result.get("appointment") or {}
        data.extra["appointment_id"] = appointment.get("id")
        return {
            "ok": True,
            "confirmation_code": appointment.get("confirmation_code"),
            "appointment": appointment,
        }

    @function_tool()
    async def reschedule_appointment(
        context: RunContext,
        appointment_id: str,
        starts_at: str,
        caller_confirmed: bool,
    ) -> dict[str, Any]:
        """Reschedule an existing appointment after the caller confirms the new time.

        Args:
            appointment_id: Appointment id from a prior booking.
            starts_at: New slot start from get_available_slots.
            caller_confirmed: Must be true only after verbal confirmation.
        """
        _reject_tenant_override()
        if not caller_confirmed:
            raise ToolError(
                "Please confirm the new appointment time with the caller before rescheduling."
            )
        data = _userdata(context)
        context.disallow_interruptions()
        try:
            result = client.reschedule_appointment(
                tenant_id=data.tenant_id,
                appointment_id=appointment_id,
                starts_at=starts_at,
            )
        except PlatformSchedulingError as exc:
            if exc.code == "slot_unavailable":
                raise ToolError(
                    "That new time is not available. Please offer another slot."
                ) from exc
            raise ToolError(
                "I could not reschedule that appointment. Please try again."
            ) from exc
        appointment = result.get("appointment") or {}
        return {
            "ok": True,
            "confirmation_code": appointment.get("confirmation_code"),
            "appointment": appointment,
        }

    @function_tool()
    async def cancel_appointment(
        context: RunContext,
        appointment_id: str,
        caller_confirmed: bool,
    ) -> dict[str, Any]:
        """Cancel an existing appointment after the caller confirms cancellation.

        Args:
            appointment_id: Appointment id to cancel.
            caller_confirmed: Must be true only after verbal confirmation.
        """
        _reject_tenant_override()
        if not caller_confirmed:
            raise ToolError(
                "Please confirm with the caller that they want to cancel before proceeding."
            )
        data = _userdata(context)
        context.disallow_interruptions()
        try:
            result = client.cancel_appointment(
                tenant_id=data.tenant_id,
                appointment_id=appointment_id,
            )
        except PlatformSchedulingError as exc:
            raise ToolError(
                "I could not cancel that appointment. Please try again."
            ) from exc
        appointment = result.get("appointment") or {}
        return {"ok": True, "appointment": appointment}

    return [
        get_available_slots,
        book_appointment,
        reschedule_appointment,
        cancel_appointment,
    ]
