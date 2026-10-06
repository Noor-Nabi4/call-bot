"""Industry template copy stays trigger-action without weakening safety."""

from __future__ import annotations

from callbot_platform.agent_templates import get_template


def test_medical_custom_instructions_are_trigger_based() -> None:
    tpl = get_template("medical")
    assert tpl is not None
    text = tpl.custom_instructions or ""
    assert "clinical" in text.lower()
    assert "Do not give medical advice" in text
    assert not text.startswith("Always ")


def test_insurance_custom_instructions_keep_no_bind_coverage() -> None:
    tpl = get_template("insurance")
    assert tpl is not None
    text = tpl.custom_instructions or ""
    assert "Do not bind coverage" in text
    assert "escalate" in text.lower()


def test_collections_custom_instructions_are_conditional() -> None:
    tpl = get_template("collections")
    assert tpl is not None
    text = tpl.custom_instructions or ""
    assert "handoff" in text.lower()
    assert "Do not threaten" in text
    assert "every turn" in text
