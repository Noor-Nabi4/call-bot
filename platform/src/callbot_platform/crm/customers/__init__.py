"""Customer CRM domain services (Phase 4)."""

from __future__ import annotations

from callbot_platform.crm.customers.service import CustomerService
from callbot_platform.crm.customers.status import CUSTOMER_STATUSES, CustomerStatus

__all__ = [
    "CUSTOMER_STATUSES",
    "CustomerService",
    "CustomerStatus",
]
