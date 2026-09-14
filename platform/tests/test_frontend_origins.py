"""Unified marketing + ops frontend origin defaults."""

from __future__ import annotations

from callbot_platform.config import Settings


def test_unified_frontend_url_defaults() -> None:
    fields = Settings.model_fields
    assert fields["ops_cors_origins"].default == "http://localhost:3002"
    assert (
        fields["stripe_checkout_success_url"].default
        == "http://localhost:3002/settings/billing?checkout=success"
    )
    assert (
        fields["stripe_checkout_cancel_url"].default
        == "http://localhost:3002/signup?canceled=1"
    )
    assert (
        fields["stripe_portal_return_url"].default
        == "http://localhost:3002/settings/billing"
    )
