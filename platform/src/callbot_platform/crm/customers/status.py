"""Controlled customer business statuses (archive is separate via archived_at)."""

from __future__ import annotations

from enum import Enum


class CustomerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


CUSTOMER_STATUSES: frozenset[str] = frozenset(s.value for s in CustomerStatus)

DEFAULT_CUSTOMER_STATUS = CustomerStatus.ACTIVE.value
