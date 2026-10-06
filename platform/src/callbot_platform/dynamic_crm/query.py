"""Controlled filter AST → parameterized SQL for custom field values."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import Select, Text, and_, cast, select
from sqlalchemy.orm import Session

from callbot_platform.db.models.crm_config import OrganizationCrmField
from callbot_platform.db.models.dynamic_crm import CrmCustomFieldValue
from callbot_platform.dynamic_crm.errors import DynamicCrmError
from callbot_platform.dynamic_crm.types import FIELD_OPERATORS, normalize_field_type

_MAX_IN_LIST = 50
_FIELD_KEY_RE = __import__("re").compile(r"^[a-z][a-z0-9_]{0,62}$")


def _escape_like(value: str) -> str:
    """Escape ILIKE metacharacters so user input cannot inject wildcards."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _coerce_number(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DynamicCrmError(
            "invalid_filter_value", "Invalid numeric filter value"
        ) from exc


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise DynamicCrmError("invalid_filter_value", "Invalid boolean filter value")


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise DynamicCrmError(
            "invalid_filter_value", "Invalid date filter value"
        ) from exc


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DynamicCrmError(
            "invalid_filter_value", "Invalid datetime filter value"
        ) from exc


def apply_field_filters(
    session: Session,
    tenant_id: UUID,
    *,
    owner_scope: str,
    owner_key: str,
    filters: list[dict[str, Any]],
    limit: int = 50,
) -> list[UUID]:
    if not filters:
        raise DynamicCrmError("empty_filters", "At least one filter is required")
    if len(filters) > 10:
        raise DynamicCrmError("too_many_filters", "Maximum 10 filters allowed")
    limit = max(1, min(int(limit), 200))

    defs = {
        d.field_key: d
        for d in session.scalars(
            select(OrganizationCrmField).where(
                OrganizationCrmField.tenant_id == tenant_id,
                OrganizationCrmField.owner_scope == owner_scope,
                OrganizationCrmField.owner_key == owner_key,
                OrganizationCrmField.enabled.is_(True),
            )
        ).all()
    }

    # AND together EXISTS-style predicates on the same record_id set.
    base = select(CrmCustomFieldValue.record_id).where(
        CrmCustomFieldValue.tenant_id == tenant_id
    )
    for raw in filters:
        if not isinstance(raw, dict):
            raise DynamicCrmError("invalid_filter", "Each filter must be an object")
        # Reject unknown AST keys that look like SQL injection attempts.
        allowed_keys = {"field", "operator", "value"}
        extra = set(raw.keys()) - allowed_keys
        if extra:
            raise DynamicCrmError(
                "invalid_filter",
                f"Unsupported filter keys: {', '.join(sorted(extra))}",
            )
        field_key = str(raw.get("field") or "").strip()
        operator = str(raw.get("operator") or "").strip()
        value = raw.get("value")
        if not _FIELD_KEY_RE.match(field_key):
            raise DynamicCrmError("unknown_field", f"Unknown field: {field_key}")
        if not operator or not operator.replace("_", "").isalnum():
            raise DynamicCrmError("invalid_operator", f"Invalid operator: {operator}")
        definition = defs.get(field_key)
        if definition is None:
            raise DynamicCrmError("unknown_field", f"Unknown field: {field_key}")
        ftype = normalize_field_type(definition.field_type)
        allowed = FIELD_OPERATORS.get(ftype, frozenset())
        if operator not in allowed:
            raise DynamicCrmError(
                "invalid_operator",
                f"Operator {operator} not allowed for type {ftype}",
            )

        sub = select(CrmCustomFieldValue.record_id).where(
            CrmCustomFieldValue.tenant_id == tenant_id,
            CrmCustomFieldValue.field_definition_id == definition.id,
        )
        sub = _apply_operator(sub, ftype, operator, value)
        base = base.where(CrmCustomFieldValue.record_id.in_(sub))

    rows = session.scalars(base.distinct().limit(limit)).all()
    return list(rows)


def _apply_operator(
    q: Select[tuple[UUID]],
    ftype: str,
    operator: str,
    value: Any,
) -> Select[tuple[UUID]]:
    if operator == "is_null":
        if ftype in {"NUMBER", "CURRENCY"}:
            return q.where(CrmCustomFieldValue.value_number.is_(None))
        if ftype == "BOOLEAN":
            return q.where(CrmCustomFieldValue.value_boolean.is_(None))
        if ftype == "DATE":
            return q.where(CrmCustomFieldValue.value_date.is_(None))
        if ftype == "DATETIME":
            return q.where(CrmCustomFieldValue.value_datetime.is_(None))
        if ftype in {"MULTI_SELECT", "ADDRESS", "FILE"}:
            return q.where(CrmCustomFieldValue.value_json.is_(None))
        return q.where(CrmCustomFieldValue.value_text.is_(None))

    if ftype in {"NUMBER", "CURRENCY"}:
        num = _coerce_number(value)
        col = CrmCustomFieldValue.value_number
        if operator == "equals":
            return q.where(col == num)
        if operator == "gt":
            return q.where(col > num)
        if operator == "gte":
            return q.where(col >= num)
        if operator == "lt":
            return q.where(col < num)
        if operator == "lte":
            return q.where(col <= num)

    if ftype == "BOOLEAN" and operator == "equals":
        return q.where(CrmCustomFieldValue.value_boolean.is_(_coerce_bool(value)))

    if ftype == "DATE":
        col = CrmCustomFieldValue.value_date
        if operator == "equals":
            return q.where(col == _coerce_date(value))
        if operator == "before":
            return q.where(col < _coerce_date(value))
        if operator == "after":
            return q.where(col > _coerce_date(value))
        if operator == "between":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise DynamicCrmError(
                    "invalid_filter_value", "between requires [start, end]"
                )
            return q.where(
                and_(col >= _coerce_date(value[0]), col <= _coerce_date(value[1]))
            )

    if ftype == "DATETIME":
        col = CrmCustomFieldValue.value_datetime
        if operator == "equals":
            return q.where(col == _coerce_datetime(value))
        if operator == "before":
            return q.where(col < _coerce_datetime(value))
        if operator == "after":
            return q.where(col > _coerce_datetime(value))
        if operator == "between":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise DynamicCrmError(
                    "invalid_filter_value", "between requires [start, end]"
                )
            return q.where(
                and_(
                    col >= _coerce_datetime(value[0]),
                    col <= _coerce_datetime(value[1]),
                )
            )

    if ftype == "DROPDOWN":
        if operator == "equals":
            return q.where(CrmCustomFieldValue.value_text == str(value))
        if operator == "in":
            if not isinstance(value, list):
                raise DynamicCrmError("invalid_filter_value", "in requires a list")
            if len(value) > _MAX_IN_LIST:
                raise DynamicCrmError(
                    "invalid_filter_value",
                    f"in list cannot exceed {_MAX_IN_LIST} values",
                )
            return q.where(CrmCustomFieldValue.value_text.in_([str(v) for v in value]))

    if ftype == "MULTI_SELECT" and operator in {"contains", "in"}:
        needle = value if isinstance(value, list) else [value]
        if len(needle) > _MAX_IN_LIST:
            raise DynamicCrmError(
                "invalid_filter_value",
                f"list cannot exceed {_MAX_IN_LIST} values",
            )
        return q.where(
            CrmCustomFieldValue.value_json.contains([str(v) for v in needle])
        )

    if ftype == "ADDRESS" and operator == "contains":
        text = _escape_like(str(value))
        return q.where(
            cast(CrmCustomFieldValue.value_json, Text).ilike(f"%{text}%", escape="\\")
        )

    if ftype in {"TEXT", "EMAIL", "PHONE", "URL", "RELATIONSHIP"}:
        col = CrmCustomFieldValue.value_text
        text = str(value)
        if operator == "equals":
            return q.where(col == text)
        escaped = _escape_like(text)
        if operator == "contains":
            return q.where(col.ilike(f"%{escaped}%", escape="\\"))
        if operator == "starts_with":
            return q.where(col.ilike(f"{escaped}%", escape="\\"))
        if operator == "ends_with":
            return q.where(col.ilike(f"%{escaped}", escape="\\"))

    raise DynamicCrmError("invalid_operator", f"Unhandled operator: {operator}")
