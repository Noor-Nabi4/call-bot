"""Structured logging helpers without secrets or raw audio."""

from __future__ import annotations

import logging
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Log a structured event. Never pass secrets or full transcripts here."""
    safe = {key: value for key, value in fields.items() if value is not None}
    if safe:
        logger.log(level, "%s | %s", message, safe)
    else:
        logger.log(level, message)
