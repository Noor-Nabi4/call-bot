"""Authoritative metric definitions for Phase 27 analytics.

Formulas here are the single source of truth; the service must not diverge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    label: str
    source: str
    numerator: str
    denominator: str
    exclusions: str
    availability: str  # "available" | "conditional" | "unavailable"
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "source": self.source,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "exclusions": self.exclusions,
            "availability": self.availability,
            "notes": self.notes,
        }


# --- Calls -----------------------------------------------------------------

CALL_TOTAL = MetricDefinition(
    id="calls.total",
    label="Total calls",
    source="calls",
    numerator="COUNT(calls) where started_at in range",
    denominator="n/a",
    exclusions="None",
    availability="available",
)

CALL_ANSWER_RATE = MetricDefinition(
    id="calls.answer_rate",
    label="Answer rate",
    source="calls.disposition_code",
    numerator="ended calls with disposition not in {no_answer, abandoned}",
    denominator="ended calls with disposition_code set",
    exclusions="Calls without QA disposition (not in denominator)",
    availability="conditional",
    notes=(
        "True PSTN ring/answer rate is unavailable without carrier CDR. "
        "When quality dispositions exist, answer_rate is reviewed-call based."
    ),
)

CALL_MISSED = MetricDefinition(
    id="calls.missed",
    label="Missed calls",
    source="calls.disposition_code",
    numerator="COUNT disposition_code == no_answer",
    denominator="n/a",
    exclusions="Calls without disposition are not counted as missed",
    availability="conditional",
    notes="Null when no disposition reviews exist in the window.",
)

CALL_AVG_DURATION = MetricDefinition(
    id="calls.average_duration_seconds",
    label="Average duration",
    source="calls.billable_seconds / started_at+ended_at",
    numerator="SUM(billable duration of ended calls)",
    denominator="COUNT(ended calls)",
    exclusions="Active (non-ended) calls",
    availability="available",
)

CALL_TRANSFER_RATE = MetricDefinition(
    id="calls.transfer_rate",
    label="Transfer rate",
    source="calls.metrics.handoff_requested | transfer_kind",
    numerator="ended calls with handoff_requested or transfer_kind != none",
    denominator="COUNT(ended calls)",
    exclusions="Active calls",
    availability="available",
    notes="Aligned with Phase 26 handoff_rate / AI handoff signal.",
)

CALL_AI_RESOLUTION = MetricDefinition(
    id="calls.ai_resolution_rate",
    label="AI resolution rate",
    source="calls.metrics + ended_at",
    numerator="ended calls without handoff",
    denominator="COUNT(ended calls)",
    exclusions="Active calls; handoffs counted as unresolved by AI",
    availability="available",
    notes="Same definition as Phase 26: (ended - handoffs) / ended.",
)

# --- Sales -----------------------------------------------------------------

SALES_LEADS = MetricDefinition(
    id="sales.leads",
    label="Leads",
    source="leads",
    numerator="COUNT non-archived leads created in range",
    denominator="n/a",
    exclusions="archived_at IS NOT NULL",
    availability="available",
)

SALES_QUALIFIED = MetricDefinition(
    id="sales.qualified_leads",
    label="Qualified leads",
    source="leads.status",
    numerator=(
        "leads created in range with status in QUALIFIED, CONTACTED, BOOKED, WON"
    ),
    denominator="n/a",
    exclusions="NEW and LOST never-qualified; archived",
    availability="available",
    notes="Pipeline past NEW implies qualification (CONTACTED requires QUALIFIED).",
)

SALES_BOOKINGS = MetricDefinition(
    id="sales.bookings",
    label="Bookings",
    source="appointments",
    numerator="appointments created in range excluding CANCELLED",
    denominator="n/a",
    exclusions="CANCELLED",
    availability="available",
)

SALES_CONVERSION = MetricDefinition(
    id="sales.conversion_rate",
    label="Lead conversion",
    source="leads.status",
    numerator="leads created in range with status in BOOKED, WON",
    denominator="leads created in range (non-archived)",
    exclusions="archived",
    availability="available",
    notes="Status-based; not payment-attributed.",
)

SALES_REV_PER_LEAD = MetricDefinition(
    id="sales.revenue_per_lead",
    label="Revenue per lead",
    source="payments ↔ leads",
    numerator="n/a",
    denominator="n/a",
    exclusions="n/a",
    availability="unavailable",
    notes="No lead→payment attribution path; aggregate ratio would mislead.",
)

SALES_REV_PER_CALL = MetricDefinition(
    id="sales.revenue_per_call",
    label="Revenue per call",
    source="payments ↔ calls",
    numerator="n/a",
    denominator="n/a",
    exclusions="n/a",
    availability="unavailable",
    notes="No call→payment attribution path; aggregate ratio would mislead.",
)

SALES_PRODUCT = MetricDefinition(
    id="sales.product_sales",
    label="Product sales",
    source="order_items + orders",
    numerator="SUM(order_items.line_total) for non-draft/cancelled/refunded orders",
    denominator="n/a",
    exclusions="DRAFT, CANCELLED, REFUNDED orders; archived orders",
    availability="available",
)

# --- Operations ------------------------------------------------------------

OPS_COMPLETED = MetricDefinition(
    id="operations.jobs_completed",
    label="Jobs completed",
    source="jobs",
    numerator="COUNT status==COMPLETED with completed_at in range",
    denominator="n/a",
    exclusions="Other statuses",
    availability="available",
)

OPS_CANCEL_RATE = MetricDefinition(
    id="operations.cancellation_rate",
    label="Cancellation rate",
    source="jobs.status",
    numerator="jobs created in range with status CANCELLED",
    denominator="jobs created in range with status != NEW",
    exclusions="Still-NEW jobs (never scheduled)",
    availability="available",
)

OPS_NO_SHOW = MetricDefinition(
    id="operations.no_show_rate",
    label="No-show rate",
    source="jobs.status + appointments.status",
    numerator="NO_SHOW jobs (created in range) + NO_SHOW appointments (created in range)",
    denominator="terminal jobs/appts in range (COMPLETED+CANCELLED+NO_SHOW)",
    exclusions="Non-terminal statuses",
    availability="available",
    notes="Uses explicit NO_SHOW status only.",
)

OPS_UTILIZATION = MetricDefinition(
    id="operations.technician_utilization",
    label="Technician utilization",
    source="technician schedules + job windows",
    numerator="n/a",
    denominator="n/a",
    exclusions="n/a",
    availability="unavailable",
    notes=(
        "Occupied/available hours require reliable clocked working time. "
        "Schedule templates alone are insufficient for production utilization %."
    ),
)

OPS_AVG_DURATION = MetricDefinition(
    id="operations.average_job_duration_seconds",
    label="Average job duration",
    source="jobs.scheduled_starts_at/ends_at + completed_at",
    numerator="SUM(scheduled_ends_at - scheduled_starts_at) for COMPLETED with both set",
    denominator="COUNT eligible completed jobs with scheduled window",
    exclusions="Completed jobs missing scheduled window; cancelled/no-show",
    availability="conditional",
    notes=(
        "No job.started_at column. Uses scheduled window as authoritative "
        "planned duration for completed jobs. Null when none eligible."
    ),
)

OPS_RESPONSE = MetricDefinition(
    id="operations.avg_lead_response_seconds",
    label="Avg lead response time",
    source="lead_activities CONTACTED - leads.created_at",
    numerator="SUM(first CONTACTED activity - lead.created_at)",
    denominator="leads with a CONTACTED activity in range",
    exclusions="Leads never contacted",
    availability="conditional",
    notes="Labeled as lead response time, not generic response time.",
)

ALL_DEFINITIONS: tuple[MetricDefinition, ...] = (
    CALL_TOTAL,
    CALL_ANSWER_RATE,
    CALL_MISSED,
    CALL_AVG_DURATION,
    CALL_TRANSFER_RATE,
    CALL_AI_RESOLUTION,
    SALES_LEADS,
    SALES_QUALIFIED,
    SALES_BOOKINGS,
    SALES_CONVERSION,
    SALES_REV_PER_LEAD,
    SALES_REV_PER_CALL,
    SALES_PRODUCT,
    OPS_COMPLETED,
    OPS_CANCEL_RATE,
    OPS_NO_SHOW,
    OPS_UTILIZATION,
    OPS_AVG_DURATION,
    OPS_RESPONSE,
)
