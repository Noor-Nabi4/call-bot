"""Phase 23 Call Intelligence enrichment layer."""

from __future__ import annotations

from callbot_platform.call_intelligence.errors import CallIntelligenceError
from callbot_platform.call_intelligence.pipeline import CallIntelligenceService

__all__ = ["CallIntelligenceError", "CallIntelligenceService"]
