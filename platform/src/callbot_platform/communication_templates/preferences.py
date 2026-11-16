"""Customer communication preference checks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.communication_templates.constants import MARKETING_TEMPLATE_KEYS
from callbot_platform.db.models import Customer


def customer_allows(
    session: Session,
    *,
    tenant_id: UUID,
    customer_id: UUID | None,
    channel: str,
    template_key: str,
) -> tuple[bool, str | None]:
    """Return (allowed, skip_reason). Missing customer → allow (recipient may be resolved later)."""
    if customer_id is None:
        return True, None
    row = session.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.tenant_id == tenant_id
        )
    )
    if row is None:
        return True, None

    channel_u = channel.upper()
    is_marketing = template_key in MARKETING_TEMPLATE_KEYS

    if channel_u == "SMS":
        if not getattr(row, "sms_allowed", True):
            return False, "sms_opted_out"
        if is_marketing and not getattr(row, "marketing_sms_allowed", True):
            return False, "marketing_sms_opted_out"
    elif channel_u == "EMAIL":
        if not getattr(row, "email_allowed", True):
            return False, "email_opted_out"
        if is_marketing and not getattr(row, "marketing_email_allowed", True):
            return False, "marketing_email_opted_out"
    return True, None
