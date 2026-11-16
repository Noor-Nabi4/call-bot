"""Deterministic paragraph-aware chunking for knowledge text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from callbot_platform.knowledge.constants import (
    CHUNK_MAX_CHARS,
    CHUNK_OVERLAP_CHARS,
    CHUNK_TARGET_CHARS,
)


@dataclass(slots=True)
class TextChunk:
    chunk_index: int
    text: str
    page_number: int | None = None
    section: str | None = None
    metadata: dict[str, Any] | None = None


def chunk_text(
    text: str,
    *,
    target_chars: int = CHUNK_TARGET_CHARS,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[TextChunk]:
    body = (text or "").strip()
    if not body:
        return []
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [body]

    chunks: list[TextChunk] = []
    buf = ""
    page: int | None = None
    section: str | None = None

    def flush() -> None:
        nonlocal buf
        cleaned = buf.strip()
        if not cleaned:
            buf = ""
            return
        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                text=cleaned[:max_chars],
                page_number=page,
                section=section,
            )
        )
        buf = (
            cleaned[-overlap:]
            if overlap > 0 and len(cleaned) > overlap
            else ""
        )

    for para in paragraphs:
        page_m = None
        if para.startswith("[Page ") and "]" in para[:20]:
            try:
                page = int(para[6 : para.index("]")])
            except ValueError:
                page = page
            page_m = para
        if para.startswith("#"):
            section = para.lstrip("#").strip()[:255]
        candidate = f"{buf}\n\n{para}".strip() if buf else para
        if len(candidate) <= target_chars:
            buf = candidate
            continue
        if buf:
            flush()
            candidate = para
        while len(candidate) > max_chars:
            window = candidate[:max_chars]
            # Prefer sentence boundary.
            cut = max(window.rfind(". "), window.rfind("\n"), window.rfind(" "))
            if cut < max_chars // 2:
                cut = max_chars
            piece = candidate[:cut].strip()
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    text=piece,
                    page_number=page,
                    section=section,
                )
            )
            start = max(0, cut - overlap)
            candidate = candidate[start:].strip()
        buf = candidate
        _ = page_m

    if buf.strip():
        flush()
    # Re-index after all flushes (flush may create with interim indexes).
    for i, c in enumerate(chunks):
        c.chunk_index = i
    return chunks
