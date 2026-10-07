"""SMS AI orchestrator — channel adapter over Phase 14 tools."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.customers import CustomerService
from callbot_platform.db.models.sms import SmsConversation, SmsMessage
from callbot_platform.sms_agent.brain import RuleBasedSmsBrain, SmsTurnPlan
from callbot_platform.sms_agent.constants import DEFAULT_CONTEXT_MESSAGES
from callbot_platform.sms_agent.conversations import SmsConversationService
from callbot_platform.sms_agent.outbound import SmsOutboundService
from callbot_platform.sms_agent.tool_bridge import SmsToolBridge
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

_STOP = frozenset(
    {
        "need",
        "want",
        "have",
        "please",
        "book",
        "booking",
        "appointment",
        "schedule",
        "service",
        "tomorrow",
        "today",
        "the",
        "and",
        "for",
        "an",
        "a",
        "my",
        "me",
        "to",
        "get",
        "help",
        "with",
        "can",
        "you",
        "i",
    }
)


def _service_search_query(body: str) -> str:
    """Derive a short search term — domain search is ILIKE on the whole string."""
    tokens = re.findall(r"[A-Za-z]{2,}", body or "")
    keep = [t for t in tokens if t.lower() not in _STOP]
    if not keep:
        return ""
    for preferred in (
        "hvac",
        "ac",
        "repair",
        "plumber",
        "heating",
        "cooling",
        "install",
    ):
        for t in keep:
            if t.lower() == preferred:
                return t
    return max(keep, key=len)


def _format_slot_label(starts_at: str, *, timezone: str = "UTC") -> str:
    try:
        dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        local = dt.astimezone(ZoneInfo(timezone))
        return local.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return starts_at


class SmsAgentOrchestrator:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        brain: RuleBasedSmsBrain | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._brain = brain or RuleBasedSmsBrain()
        self._conversations = SmsConversationService(session)
        self._outbound = SmsOutboundService(session)
        self._tools = SmsToolBridge(
            session, hmac_secret=self._settings.metadata_hmac_secret or ""
        )

    def handle_inbound_message(
        self,
        *,
        conversation: SmsConversation,
        inbound: SmsMessage,
        customer: dict[str, Any] | None,
    ) -> dict[str, Any]:
        logger.info(
            "sms.ai.started tenant_id=%s conversation_id=%s message_id=%s",
            conversation.tenant_id,
            conversation.id,
            inbound.id,
        )
        history = self._conversations.load_context(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            limit=DEFAULT_CONTEXT_MESSAGES,
        )
        plan = self._brain.plan_turn(
            body=inbound.body,
            workflow=dict(conversation.workflow_state or {}),
            customer=customer,
            history=history,
        )
        inbound.intent = plan.intent
        try:
            reply = self._execute_plan(
                conversation=conversation,
                inbound=inbound,
                customer=customer,
                plan=plan,
            )
            outbound = self._outbound.enqueue_reply(
                conversation=conversation,
                body=reply,
                idempotency_key=f"sms_reply:{inbound.id}",
                operation_id=inbound.operation_id,
                customer_id=conversation.customer_id,
            )
            logger.info(
                "sms.ai.completed tenant_id=%s conversation_id=%s message_id=%s",
                conversation.tenant_id,
                conversation.id,
                inbound.id,
            )
            return {"reply": reply, "outbound": outbound, "intent": plan.intent}
        except Exception:
            logger.exception(
                "sms.ai.failed tenant_id=%s conversation_id=%s message_id=%s",
                conversation.tenant_id,
                conversation.id,
                inbound.id,
            )
            raise

    def _execute_plan(
        self,
        *,
        conversation: SmsConversation,
        inbound: SmsMessage,
        customer: dict[str, Any] | None,
        plan: SmsTurnPlan,
    ) -> str:
        customer_id = (
            UUID(str(customer["id"]))
            if customer and customer.get("id")
            else conversation.customer_id
        )
        phone = conversation.phone_e164

        if plan.is_rejection:
            self._conversations.clear_workflow_keys(
                conversation,
                [
                    "pending_confirmation",
                    "booking_args",
                    "confirmation_token",
                    "operation_id",
                ],
            )
            return plan.reply or "Okay — cancelled."

        if plan.is_confirmation:
            return self._confirm_booking(
                conversation=conversation,
                customer_id=customer_id,
                phone=phone,
            )

        if plan.select_slot_index is not None:
            return self._select_slot(
                conversation=conversation,
                customer_id=customer_id,
                phone=phone,
                index=plan.select_slot_index,
            )

        if plan.reply and not plan.tool_calls:
            return plan.reply

        if plan.intent in {"BOOKING", "AVAILABILITY"}:
            return self._booking_availability_flow(
                conversation=conversation,
                inbound=inbound,
                customer_id=customer_id,
                phone=phone,
                query=inbound.body,
            )

        if plan.intent == "HUMAN_HANDOFF":
            result = self._tools.invoke(
                "request_human",
                tenant_id=conversation.tenant_id,
                args={
                    "reason": "CUSTOMER_REQUEST",
                    "summary": (inbound.body or "")[:500],
                },
                customer_id=customer_id,
                caller_phone=phone,
                operation_id=uuid.uuid4(),
            )
            write_audit(
                self._session,
                tenant_id=conversation.tenant_id,
                actor="AI_SMS_AGENT",
                action="sms_handoff_requested",
                resource_ids={
                    "conversation_id": str(conversation.id),
                    "message_id": str(inbound.id),
                },
            )
            if result.get("ok"):
                conversation.status = "HANDOFF"
                return (
                    "I've asked a teammate to follow up with you. "
                    "Someone will reach out as soon as they can."
                )
            return self._tools.customer_safe(result) or (
                "I wasn't able to connect you with a teammate right now."
            )

        if plan.intent == "PRODUCT_QUESTION":
            result = self._tools.invoke(
                "search_products",
                tenant_id=conversation.tenant_id,
                args={"query": inbound.body, "limit": 5},
                customer_id=customer_id,
                caller_phone=phone,
            )
            if not result.get("ok"):
                return self._tools.customer_safe(result)
            products = (result.get("data") or {}).get("products") or []
            if not products:
                return (
                    "I couldn't find that product in stock right now, "
                    "but I can help you find an alternative."
                )
            names = [
                str(p.get("name") or p.get("title") or "item") for p in products[:3]
            ]
            return "Here's what I found: " + "; ".join(names) + ". Want details on one?"

        if plan.intent == "ORDER_STATUS":
            result = self._tools.invoke(
                "find_orders",
                tenant_id=conversation.tenant_id,
                args={},
                customer_id=customer_id,
                caller_phone=phone,
            )
            if not result.get("ok"):
                return self._tools.customer_safe(result)
            orders = (result.get("data") or {}).get("orders") or []
            if not orders:
                return "I don't see recent orders on your account."
            o = orders[0]
            return (
                f"Your latest order {o.get('orderNumber') or o.get('id')} "
                f"is {o.get('status')}. Total {o.get('total')} {o.get('currency') or ''}."
            ).strip()

        if plan.intent == "GENERAL_QUESTION" or any(
            (c.get("tool") == "search_knowledge") for c in plan.tool_calls
        ):
            result = self._tools.invoke(
                "search_knowledge",
                tenant_id=conversation.tenant_id,
                args={"query": inbound.body, "topK": 3},
                customer_id=customer_id,
                caller_phone=phone,
            )
            if not result.get("ok"):
                return self._tools.customer_safe(result)
            data = result.get("data") or {}
            if data.get("status") == "NO_RELEVANT_KNOWLEDGE" or not data.get("results"):
                return (
                    "I don't have enough information on that in our knowledge base. "
                    "I can help with booking, products, or order status."
                )
            top = (data.get("results") or [])[0]
            snippet = str(top.get("content") or "")[:280].strip()
            return snippet or (
                "I found related information, but need a more specific question."
            )

        return plan.reply or (
            "Thanks for your message. How can I help with booking, products, or orders?"
        )

    def _booking_availability_flow(
        self,
        *,
        conversation: SmsConversation,
        inbound: SmsMessage,
        customer_id: UUID | None,
        phone: str,
        query: str,
    ) -> str:
        if customer_id is None:
            return (
                "I don't have this number on file yet. "
                "Please share your first name to get started, or call us to book."
            )
        q = _service_search_query(query)
        services = self._tools.invoke(
            "search_services",
            tenant_id=conversation.tenant_id,
            args={"query": q or " ", "limit": 5},
            customer_id=customer_id,
            caller_phone=phone,
        )
        if not services.get("ok"):
            return self._tools.customer_safe(services)
        items = (services.get("data") or {}).get("services") or []
        if not items and q:
            services = self._tools.invoke(
                "search_services",
                tenant_id=conversation.tenant_id,
                args={"query": " ", "limit": 5},
                customer_id=customer_id,
                caller_phone=phone,
            )
            if not services.get("ok"):
                return self._tools.customer_safe(services)
            items = (services.get("data") or {}).get("services") or []
        if not items:
            return (
                "I couldn't find a matching service. Could you describe what you need?"
            )
        service = items[0]
        service_id = str(service["id"])
        # Prefer a weekday window so default business hours produce slots.
        start_day = (datetime.now(UTC) + timedelta(days=1)).date()
        while start_day.weekday() >= 5:
            start_day += timedelta(days=1)
        end_day = start_day + timedelta(days=6)
        avail = self._tools.invoke(
            "check_availability",
            tenant_id=conversation.tenant_id,
            args={
                "serviceId": service_id,
                "preferredStartDate": start_day.isoformat(),
                "preferredEndDate": end_day.isoformat(),
                "limit": 3,
            },
            customer_id=customer_id,
            caller_phone=phone,
        )
        if not avail.get("ok"):
            code = ((avail.get("error") or {}).get("code")) or ""
            if code == "availability_empty":
                return (
                    "I don't see an opening that matches those times. Want another day?"
                )
            return self._tools.customer_safe(avail)
        slots_raw = (
            (avail.get("data") or {}).get("slots")
            or (avail.get("data") or {}).get("availability")
            or []
        )
        if not slots_raw:
            return "I don't see an opening that matches those times. Want another day?"
        timezone = "UTC"
        offered: list[dict[str, Any]] = []
        lines = [
            f"I can help with {service.get('name') or 'that service'}. Available times:"
        ]
        for i, slot in enumerate(slots_raw[:3], start=1):
            starts = str(
                slot.get("startsAt") or slot.get("starts_at") or slot.get("start") or ""
            )
            ends = str(
                slot.get("endsAt") or slot.get("ends_at") or slot.get("end") or ""
            )
            tz = str(slot.get("timezone") or timezone)
            label = _format_slot_label(starts, timezone=tz)
            lines.append(f"{i}. {label}")
            offered.append(
                {
                    "startsAt": starts,
                    "endsAt": ends,
                    "timezone": tz,
                    "serviceId": service_id,
                    "serviceName": service.get("name"),
                    "technicianId": slot.get("technicianId")
                    or slot.get("technician_id"),
                    "locationId": slot.get("locationId") or slot.get("location_id"),
                    "label": label,
                }
            )
        lines.append("Which works best?")
        self._conversations.update_workflow(
            conversation,
            {
                "offered_slots": offered,
                "service_id": service_id,
                "offered_at": datetime.now(UTC).isoformat(),
            },
        )
        write_audit(
            self._session,
            tenant_id=conversation.tenant_id,
            actor="AI_SMS_AGENT",
            action="sms.booking.started",
            resource_ids={
                "conversation_id": str(conversation.id),
                "message_id": str(inbound.id),
                "service_id": service_id,
            },
        )
        return "\n".join(lines)

    def _select_slot(
        self,
        *,
        conversation: SmsConversation,
        customer_id: UUID | None,
        phone: str,
        index: int,
    ) -> str:
        if customer_id is None:
            return "I need to identify your account before booking."
        offered = list((conversation.workflow_state or {}).get("offered_slots") or [])
        if index < 0 or index >= len(offered):
            return "Please reply with 1, 2, or 3 to pick a time."
        slot = offered[index]
        # Revalidate availability before preparing confirmation (advisory refresh).
        day = ""
        starts = str(slot.get("startsAt") or "")
        if "T" in starts:
            day = starts.split("T", 1)[0]
        avail = self._tools.invoke(
            "check_availability",
            tenant_id=conversation.tenant_id,
            args={
                "serviceId": str(slot.get("serviceId")),
                "preferredDate": day
                or (datetime.now(UTC) + timedelta(days=1)).date().isoformat(),
                "limit": 5,
            },
            customer_id=customer_id,
            caller_phone=phone,
        )
        still_open = False
        if avail.get("ok"):
            slots = (
                (avail.get("data") or {}).get("slots")
                or (avail.get("data") or {}).get("availability")
                or []
            )
            for s in slots:
                s_start = str(s.get("startsAt") or s.get("starts_at") or "")
                if s_start == starts:
                    still_open = True
                    break
        if not still_open:
            self._conversations.clear_workflow_keys(
                conversation, ["offered_slots", "pending_confirmation"]
            )
            return "That time was just taken. I can check the next available times for you."

        op = uuid.uuid4()
        booking_args: dict[str, Any] = {
            "customerId": str(customer_id),
            "serviceId": str(slot.get("serviceId")),
            "startsAt": starts,
            "endsAt": str(slot.get("endsAt")),
            "timezone": str(slot.get("timezone") or "UTC"),
            "description": f"SMS booking: {slot.get('serviceName') or 'service'}",
        }
        if slot.get("technicianId"):
            booking_args["technicianId"] = str(slot["technicianId"])
        if slot.get("locationId"):
            booking_args["locationId"] = str(slot["locationId"])

        prep = self._tools.invoke(
            "create_booking",
            tenant_id=conversation.tenant_id,
            args=booking_args,
            customer_id=customer_id,
            caller_phone=phone,
            operation_id=op,
            confirmed=False,
        )
        if prep.get("ok"):
            # Unexpected — should require confirmation
            return "Your booking is ready. Reply YES to confirm."
        err = (prep.get("error") or {}).get("code")
        if err != "confirmation_required":
            return self._tools.customer_safe(prep)
        token = prep.get("confirmationToken")
        self._conversations.update_workflow(
            conversation,
            {
                "pending_confirmation": True,
                "booking_args": booking_args,
                "confirmation_token": token,
                "operation_id": str(op),
                "offered_slots": offered,
            },
        )
        label = slot.get("label") or _format_slot_label(starts)
        return (
            f"I can book your {slot.get('serviceName') or 'appointment'} "
            f"for {label}. Reply YES to confirm."
        )

    def _confirm_booking(
        self,
        *,
        conversation: SmsConversation,
        customer_id: UUID | None,
        phone: str,
    ) -> str:
        wf = dict(conversation.workflow_state or {})
        args = wf.get("booking_args")
        token = wf.get("confirmation_token")
        op_raw = wf.get("operation_id")
        if not args or not token or not op_raw or customer_id is None:
            return (
                "I don't have a pending booking to confirm. Ask me for available times."
            )
        try:
            op = UUID(str(op_raw))
        except ValueError:
            return "That confirmation expired. Ask me for available times again."

        logger.info(
            "sms.booking.started tenant_id=%s conversation_id=%s operation_id=%s",
            conversation.tenant_id,
            conversation.id,
            op,
        )
        result = self._tools.invoke(
            "create_booking",
            tenant_id=conversation.tenant_id,
            args=dict(args),
            customer_id=customer_id,
            caller_phone=phone,
            operation_id=op,
            confirmed=True,
            confirmation_token=str(token),
        )
        if not result.get("ok"):
            code = ((result.get("error") or {}).get("code")) or ""
            logger.info(
                "sms.booking.failed tenant_id=%s operation_id=%s code=%s",
                conversation.tenant_id,
                op,
                code,
            )
            if code == "booking_conflict":
                self._conversations.clear_workflow_keys(
                    conversation,
                    [
                        "pending_confirmation",
                        "booking_args",
                        "confirmation_token",
                        "operation_id",
                        "offered_slots",
                    ],
                )
                return "That time was just taken. I can check the next available times for you."
            if code == "expired":
                self._conversations.clear_workflow_keys(
                    conversation,
                    ["pending_confirmation", "confirmation_token", "operation_id"],
                )
                return "That confirmation expired. Ask me for available times again."
            return self._tools.customer_safe(result)

        data = result.get("data") or {}
        appt = data.get("appointment") or {}
        starts = appt.get("startsAt") or args.get("startsAt")
        label = _format_slot_label(
            str(starts), timezone=str(args.get("timezone") or "UTC")
        )
        self._conversations.clear_workflow_keys(
            conversation,
            [
                "pending_confirmation",
                "booking_args",
                "confirmation_token",
                "operation_id",
                "offered_slots",
            ],
        )
        write_audit(
            self._session,
            tenant_id=conversation.tenant_id,
            actor="AI_SMS_AGENT",
            action="sms.booking.completed",
            resource_ids={
                "conversation_id": str(conversation.id),
                "operation_id": str(op),
                "appointment_id": appt.get("id"),
                "job_id": (data.get("job") or {}).get("id"),
            },
            idempotency_key=f"sms_booking_done:{op}",
        )
        logger.info(
            "sms.booking.completed tenant_id=%s operation_id=%s",
            conversation.tenant_id,
            op,
        )
        # Booking succeeded even if this confirmation SMS later fails to deliver.
        return f"You're booked for tomorrow at {label}. We'll see you then."


def identify_customer(
    session: Session, *, tenant_id: UUID, phone_e164: str
) -> dict[str, Any] | None:
    return CustomerService(session).lookup_by_phone(tenant_id, phone_e164)
