"""Safe allow-listed template rendering for automation messages."""

from __future__ import annotations

import re
from typing import Any

from callbot_platform.automations.constants import SAFE_TEMPLATE_KEYS

_TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def render_template(template: str, context: dict[str, Any]) -> str:
    """Replace {{path}} tokens from allow-listed keys only."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in SAFE_TEMPLATE_KEYS:
            return ""
        value = context.get(key)
        return "" if value is None else str(value)

    return _TOKEN.sub(repl, template or "")
