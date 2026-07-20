"""Helpers to cut first-response latency on call start."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def build_greeting_instructions(greeting_hint: str | None) -> str:
    """Tight greeting prompt — prefer a fixed line over open-ended generation."""
    hint = (greeting_hint or "").strip()
    if hint:
        return (
            "Speak this greeting to the caller now in a natural spoken voice. "
            "Keep it to one or two short sentences. Do not add extra offers or "
            f'questions beyond what is already present: "{hint}"'
        )
    return (
        "Greet the caller briefly, introduce yourself as the business voice "
        "assistant, and ask how you can help. One or two short sentences only."
    )


async def cancel_task(task: asyncio.Task[T] | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return


async def run_in_thread(fn: Callable[[], T]) -> T:
    """Offload blocking platform HTTP onto a worker thread."""
    return await asyncio.to_thread(fn)
