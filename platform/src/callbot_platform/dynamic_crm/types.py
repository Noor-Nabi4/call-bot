"""Dynamic CRM field types and controlled filter operators."""

from __future__ import annotations

from typing import Final

FIELD_TYPES: Final[frozenset[str]] = frozenset(
    {
        "TEXT",
        "NUMBER",
        "CURRENCY",
        "BOOLEAN",
        "DATE",
        "DATETIME",
        "EMAIL",
        "PHONE",
        "URL",
        "DROPDOWN",
        "MULTI_SELECT",
        "ADDRESS",
        "FILE",
        "RELATIONSHIP",
    }
)

OWNER_SCOPE_MODULE = "module"
OWNER_SCOPE_OBJECT = "object"
OWNER_SCOPES: Final[frozenset[str]] = frozenset(
    {OWNER_SCOPE_MODULE, OWNER_SCOPE_OBJECT}
)

CARDINALITY_ONE_TO_ONE = "ONE_TO_ONE"
CARDINALITY_ONE_TO_MANY = "ONE_TO_MANY"
CARDINALITY_MANY_TO_MANY = "MANY_TO_MANY"
CARDINALITIES: Final[frozenset[str]] = frozenset(
    {
        CARDINALITY_ONE_TO_ONE,
        CARDINALITY_ONE_TO_MANY,
        CARDINALITY_MANY_TO_MANY,
    }
)

# Allowed filter operators per field type (controlled AST — no free SQL).
FIELD_OPERATORS: Final[dict[str, frozenset[str]]] = {
    "TEXT": frozenset({"equals", "contains", "starts_with", "ends_with", "is_null"}),
    "NUMBER": frozenset({"equals", "gt", "gte", "lt", "lte", "is_null"}),
    "CURRENCY": frozenset({"equals", "gt", "gte", "lt", "lte", "is_null"}),
    "BOOLEAN": frozenset({"equals", "is_null"}),
    "DATE": frozenset({"equals", "before", "after", "between", "is_null"}),
    "DATETIME": frozenset({"equals", "before", "after", "between", "is_null"}),
    "EMAIL": frozenset({"equals", "contains", "is_null"}),
    "PHONE": frozenset({"equals", "contains", "is_null"}),
    "URL": frozenset({"equals", "contains", "is_null"}),
    "DROPDOWN": frozenset({"equals", "in", "is_null"}),
    "MULTI_SELECT": frozenset({"contains", "in", "is_null"}),
    "ADDRESS": frozenset({"contains", "is_null"}),
    "FILE": frozenset({"is_null"}),
    "RELATIONSHIP": frozenset({"equals", "is_null"}),
}


def normalize_field_type(value: str) -> str:
    key = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if key == "MULTISELECT":
        key = "MULTI_SELECT"
    if key not in FIELD_TYPES:
        raise ValueError(f"Unsupported field type: {value}")
    return key


def normalize_cardinality(value: str) -> str:
    key = str(value or "").strip().upper().replace("-", "_")
    aliases = {
        "1:1": CARDINALITY_ONE_TO_ONE,
        "1:N": CARDINALITY_ONE_TO_MANY,
        "N:N": CARDINALITY_MANY_TO_MANY,
        "ONE_TO_ONE": CARDINALITY_ONE_TO_ONE,
        "ONE_TO_MANY": CARDINALITY_ONE_TO_MANY,
        "MANY_TO_MANY": CARDINALITY_MANY_TO_MANY,
    }
    out = aliases.get(key, key)
    if out not in CARDINALITIES:
        raise ValueError(f"Unsupported cardinality: {value}")
    return out
