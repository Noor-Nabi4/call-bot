"""Tenant organization profile (the business entity)."""

from __future__ import annotations

from callbot_platform.organization.errors import OrganizationError
from callbot_platform.organization.repos import OrganizationRepository
from callbot_platform.organization.service import OrganizationService
from callbot_platform.organization.validation import (
    BUSINESS_TYPES,
    serialize_organization,
)

__all__ = [
    "BUSINESS_TYPES",
    "OrganizationError",
    "OrganizationRepository",
    "OrganizationService",
    "serialize_organization",
]
