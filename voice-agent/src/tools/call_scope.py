"""Shared call-scope header helper for platform HTTP clients."""

from __future__ import annotations


class CallScopeMixin:
    _call_scope: str | None = None

    def set_call_scope(self, call_scope: str | None) -> None:
        self._call_scope = call_scope

    def _scope_headers(self, base: dict[str, str]) -> dict[str, str]:
        headers = dict(base)
        if self._call_scope:
            headers["X-Call-Scope"] = self._call_scope
        return headers
