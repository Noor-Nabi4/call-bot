"""Call flow validation and rendering tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from callbot_platform.call_flow import (
    CallFlowError,
    default_call_flow,
    render_call_flow_instructions,
    validate_call_flow,
)
from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.db.models import Tenant


def test_default_flow_validates_and_renders() -> None:
    flow = validate_call_flow(default_call_flow())
    assert flow["version"] == 1
    assert len(flow["steps"]) >= 3
    text = render_call_flow_instructions(flow)
    assert "ORDERED CALL FLOW" in text
    assert "Greet" in text or "greeting" in text.lower()


def test_invalid_step_type_rejected() -> None:
    with pytest.raises(CallFlowError) as exc:
        validate_call_flow(
            {
                "version": 1,
                "steps": [
                    {
                        "id": "bad",
                        "type": "teleport",
                        "label": "Nope",
                        "enabled": True,
                    }
                ],
            }
        )
    assert exc.value.code == "invalid_call_flow"


def test_profile_persists_call_flow(session: Session, tenant: Tenant) -> None:
    repo = AgentProfileRepository(session)
    created = repo.create(
        tenant.id,
        name="Flow Agent",
        agent_type="receptionist",
        is_default=True,
        call_flow={
            "version": 1,
            "steps": [
                {
                    "id": "g1",
                    "type": "greeting",
                    "label": "Hello",
                    "instruction": "Say hi",
                    "enabled": True,
                }
            ],
        },
    )
    assert created["call_flow"]["steps"][0]["label"] == "Hello"
    profile_id = uuid.UUID(created["id"])
    updated = repo.update(
        tenant.id,
        profile_id,
        call_flow={
            "version": 1,
            "steps": [
                {
                    "id": "g1",
                    "type": "greeting",
                    "label": "Hello",
                    "enabled": True,
                },
                {
                    "id": "b1",
                    "type": "book",
                    "label": "Book",
                    "instruction": "Schedule now",
                    "enabled": True,
                },
            ],
        },
    )
    assert len(updated["call_flow"]["steps"]) == 2
    voice = repo.get_voice_profile(
        tenant.id, business_name=tenant.name, profile_id=profile_id
    )
    assert voice is not None
    assert voice["call_flow"]["steps"][1]["label"] == "Book"
