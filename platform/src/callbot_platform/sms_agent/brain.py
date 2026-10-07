"""Intent detection and SMS turn planning.

Deterministic rule-based brain is authoritative for tests and offline runs.
OpenAI may be used when configured — still only returns orchestration plans;
mutations always go through AIToolExecutor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class IntentResult:
    intent: str
    confidence: float


@dataclass
class SmsTurnPlan:
    intent: str
    confidence: float
    reply: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    select_slot_index: int | None = None
    is_confirmation: bool = False
    is_rejection: bool = False


_YES = re.compile(
    r"^\s*(y|yes|yeah|yep|sure|ok|okay|confirm|book\s*it|do\s*it|please)\s*[!.]?\s*$",
    re.I,
)
_NO = re.compile(
    r"^\s*(n|no|nope|cancel|stop|never\s*mind|dont|don't)\s*[!.]?\s*$",
    re.I,
)
_SLOT_NUM = re.compile(r"^\s*([1-9])\s*[).:]?\s*$")
_BOOKING = re.compile(
    r"\b(book|appointment|schedule|repair|service|ac|hvac|plumber|tomorrow|today)\b",
    re.I,
)
_RESCHEDULE = re.compile(
    r"\b(reschedule|move\s+(my\s+)?appointment|change\s+time)\b", re.I
)
_CANCEL = re.compile(r"\b(cancel\s+(my\s+)?appointment|cancel\s+booking)\b", re.I)
_ORDER = re.compile(r"\b(order|tracking|shipment|delivery\s+status)\b", re.I)
_PRODUCT = re.compile(r"\b(product|in\s+stock|inventory|price|how\s+much|buy)\b", re.I)
_HANDOFF = re.compile(
    r"\b(human|agent|person|representative|talk\s+to\s+someone)\b", re.I
)


def detect_intent(body: str, *, workflow: dict[str, Any] | None = None) -> IntentResult:
    text = (body or "").strip()
    wf = workflow or {}
    if wf.get("pending_confirmation") and _YES.match(text):
        return IntentResult("CONFIRMATION", 0.99)
    if wf.get("pending_confirmation") and _NO.match(text):
        return IntentResult("CONFIRMATION", 0.99)
    if wf.get("offered_slots") and (
        _SLOT_NUM.match(text)
        or re.search(r"\b(first|second|third|1:|2:|3:)\b", text, re.I)
    ):
        return IntentResult("SLOT_SELECTION", 0.95)
    if _HANDOFF.search(text):
        return IntentResult("HUMAN_HANDOFF", 0.9)
    if _RESCHEDULE.search(text):
        return IntentResult("RESCHEDULE", 0.9)
    if _CANCEL.search(text):
        return IntentResult("CANCELLATION", 0.9)
    if _ORDER.search(text):
        return IntentResult("ORDER_STATUS", 0.85)
    if _PRODUCT.search(text) and not _BOOKING.search(text):
        return IntentResult("PRODUCT_QUESTION", 0.8)
    if _BOOKING.search(text):
        return IntentResult("BOOKING", 0.9)
    if re.search(r"\b(available|availability|openings)\b", text, re.I):
        return IntentResult("AVAILABILITY", 0.85)
    if re.search(r"\b(price|cost|how much)\b", text, re.I):
        return IntentResult("PRICE", 0.85)
    return IntentResult("UNKNOWN", 0.4)


def parse_slot_selection(body: str, offered: list[dict[str, Any]]) -> int | None:
    text = (body or "").strip().lower()
    m = _SLOT_NUM.match(text)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(offered):
            return idx
    ordinals = {"first": 0, "second": 1, "third": 2, "1st": 0, "2nd": 1, "3rd": 2}
    for key, idx in ordinals.items():
        if key in text and idx < len(offered):
            return idx
    # Match by displayed time fragment
    for idx, slot in enumerate(offered):
        label = str(slot.get("label") or slot.get("startsAt") or "").lower()
        if label and label[:5] in text:
            return idx
        starts = str(slot.get("startsAt") or "")
        if "T" in starts:
            hhmm = starts.split("T", 1)[1][:5]
            if hhmm and hhmm in text:
                return idx
    return None


class RuleBasedSmsBrain:
    """Offline/test brain — produces plans without calling an LLM."""

    def plan_turn(
        self,
        *,
        body: str,
        workflow: dict[str, Any],
        customer: dict[str, Any] | None,
        history: list[dict[str, Any]],
    ) -> SmsTurnPlan:
        intent = detect_intent(body, workflow=workflow)
        if intent.intent == "CONFIRMATION":
            if _YES.match(body or ""):
                return SmsTurnPlan(
                    intent=intent.intent,
                    confidence=intent.confidence,
                    is_confirmation=True,
                )
            return SmsTurnPlan(
                intent=intent.intent,
                confidence=intent.confidence,
                is_rejection=True,
                reply="Okay — I won't book that. Tell me if you'd like other times.",
            )
        if intent.intent == "SLOT_SELECTION":
            offered = list(workflow.get("offered_slots") or [])
            idx = parse_slot_selection(body, offered)
            if idx is None:
                return SmsTurnPlan(
                    intent=intent.intent,
                    confidence=intent.confidence,
                    reply="Please reply with 1, 2, or 3 to pick a time.",
                )
            return SmsTurnPlan(
                intent=intent.intent,
                confidence=intent.confidence,
                select_slot_index=idx,
            )
        if intent.intent == "HUMAN_HANDOFF":
            return SmsTurnPlan(
                intent=intent.intent,
                confidence=intent.confidence,
                tool_calls=[
                    {
                        "tool": "request_human",
                        "args": {
                            "reason": "CUSTOMER_REQUEST",
                            "summary": (body or "")[:500],
                        },
                    }
                ],
            )
        if intent.intent in {"BOOKING", "AVAILABILITY"}:
            return SmsTurnPlan(
                intent=intent.intent,
                confidence=intent.confidence,
                tool_calls=[
                    {"tool": "search_services", "args": {"query": body, "limit": 5}}
                ],
            )
        if intent.intent == "PRODUCT_QUESTION":
            return SmsTurnPlan(
                intent=intent.intent,
                confidence=intent.confidence,
                tool_calls=[
                    {"tool": "search_products", "args": {"query": body, "limit": 5}}
                ],
            )
        if intent.intent == "ORDER_STATUS":
            if not customer:
                return SmsTurnPlan(
                    intent=intent.intent,
                    confidence=intent.confidence,
                    reply=(
                        "I couldn't match this number to a customer on file. "
                        "Please call us or share your order number with support."
                    ),
                )
            return SmsTurnPlan(
                intent=intent.intent,
                confidence=intent.confidence,
                tool_calls=[{"tool": "find_orders", "args": {}}],
            )
        if customer:
            name = customer.get("displayName") or customer.get("firstName") or ""
            greet = f"Hi {name.split()[0]} — " if name else "Hi — "
        else:
            greet = "Hi — "
        return SmsTurnPlan(
            intent=intent.intent,
            confidence=intent.confidence,
            reply=(
                f"{greet}thanks for your message. I can help with bookings, "
                "availability, products, or order status. What do you need?"
            ),
        )
