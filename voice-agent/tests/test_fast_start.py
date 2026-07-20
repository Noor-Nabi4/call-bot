"""Tests for first-response latency helpers."""

from __future__ import annotations

import asyncio

import pytest

from session.fast_start import build_greeting_instructions, cancel_task


def test_greeting_instructions_prefer_configured_line() -> None:
    text = build_greeting_instructions(
        "Thanks for calling Acme HVAC. How can I help you today?"
    )
    assert "Thanks for calling Acme HVAC" in text
    assert "one or two short sentences" in text.lower()


def test_greeting_instructions_fallback_without_hint() -> None:
    text = build_greeting_instructions(None)
    assert "ask how you can help" in text.lower()
    assert '""' not in text


def test_greeting_instructions_strip_whitespace() -> None:
    text = build_greeting_instructions("   ")
    assert "ask how you can help" in text.lower()


@pytest.mark.asyncio
async def test_cancel_task_is_idempotent() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _slow() -> None:
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    task = asyncio.create_task(_slow())
    await started.wait()
    await cancel_task(task)
    assert cancelled.is_set()
    await cancel_task(task)
    await cancel_task(None)
