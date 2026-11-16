"""Safe server-side template renderer — allow-listed variables only, fail closed."""

from __future__ import annotations

import html
import re
from typing import Any

from callbot_platform.communication_templates.constants import (
    ALL_VARIABLES,
    MAX_BODY_TEMPLATE_LEN,
    MAX_EXPANSION_DEPTH,
    MAX_RENDERED_EMAIL_LEN,
    MAX_RENDERED_SMS_LEN,
    MAX_SUBJECT_TEMPLATE_LEN,
    TEMPLATE_VARIABLES,
)
from callbot_platform.communication_templates.errors import CommunicationTemplateError

_TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_FORBIDDEN = re.compile(
    r"(?:__import__|__builtins__|eval\s*\(|exec\s*\(|"
    r"\{\{\s*(?:config|env|os|sys|secrets?)\.)",
    re.I,
)
_HTML_TAG = re.compile(r"<[^>]+>")


def extract_variables(template: str) -> set[str]:
    return {m.group(1) for m in _TOKEN.finditer(template or "")}


def validate_template_text(
    *,
    channel: str,
    template_key: str,
    body: str,
    subject: str | None = None,
) -> list[str]:
    """Return validation error messages (empty = valid)."""
    errors: list[str] = []
    channel_u = channel.upper()
    body = body or ""
    if len(body) > MAX_BODY_TEMPLATE_LEN:
        errors.append(f"Body exceeds maximum length ({MAX_BODY_TEMPLATE_LEN})")
    if _FORBIDDEN.search(body) or (subject and _FORBIDDEN.search(subject)):
        errors.append("Template contains forbidden expressions")
    if channel_u == "SMS":
        if subject:
            errors.append("SMS templates must not include a subject")
        if _HTML_TAG.search(body):
            errors.append("SMS templates must not include HTML")
    elif channel_u == "EMAIL":
        if not (subject or "").strip():
            errors.append("Email templates require a subject")
        if subject and len(subject) > MAX_SUBJECT_TEMPLATE_LEN:
            errors.append(
                f"Subject exceeds maximum length ({MAX_SUBJECT_TEMPLATE_LEN})"
            )
    else:
        errors.append(f"Invalid channel: {channel}")

    allowed = TEMPLATE_VARIABLES.get(template_key, frozenset())
    for text, _label in ((body, "body"), (subject or "", "subject")):
        for var in extract_variables(text):
            if var not in ALL_VARIABLES:
                errors.append(f"Unknown template variable: {var}")
            elif var not in allowed:
                errors.append(
                    f"Variable {var} is not available for template key {template_key}"
                )
            # Depth: only single-token {{a.b}} — nested braces already rejected by regex
            if var.count(".") > MAX_EXPANSION_DEPTH:
                errors.append(f"Variable path too deep: {var}")
    return errors


def render(
    template: str,
    context: dict[str, Any],
    *,
    channel: str,
    template_key: str,
    subject: str | None = None,
    sanitize_html: bool = True,
) -> dict[str, str]:
    """Render subject/body. Raises on unknown/disallowed variables or length."""
    errs = validate_template_text(
        channel=channel, template_key=template_key, body=template, subject=subject
    )
    if errs:
        raise CommunicationTemplateError(
            "invalid_template", "; ".join(errs), retryable=False
        )

    allowed = TEMPLATE_VARIABLES.get(template_key, frozenset())

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in allowed or key not in ALL_VARIABLES:
            raise CommunicationTemplateError(
                "unknown_variable",
                f"Unknown template variable: {key}",
                retryable=False,
            )
        value = context.get(key)
        if value is None:
            return ""
        text = str(value)
        if channel.upper() == "EMAIL" and sanitize_html:
            return html.escape(text, quote=True)
        return text

    rendered_body = _TOKEN.sub(repl, template or "")
    rendered_subject = _TOKEN.sub(repl, subject or "") if subject else ""

    if channel.upper() == "SMS":
        if len(rendered_body) > MAX_RENDERED_SMS_LEN:
            raise CommunicationTemplateError(
                "rendered_too_long",
                f"Rendered SMS exceeds {MAX_RENDERED_SMS_LEN} characters",
                retryable=False,
            )
        # Normalize whitespace for SMS
        rendered_body = re.sub(r"[ \t]+", " ", rendered_body).strip()
    else:
        total = len(rendered_subject) + len(rendered_body)
        if total > MAX_RENDERED_EMAIL_LEN:
            raise CommunicationTemplateError(
                "rendered_too_long",
                f"Rendered email exceeds {MAX_RENDERED_EMAIL_LEN} characters",
                retryable=False,
            )

    return {"subject": rendered_subject, "body": rendered_body}
