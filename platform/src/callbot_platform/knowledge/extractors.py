"""Document extractors — PDF, DOCX, text, website."""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from callbot_platform.knowledge.constants import (
    DOCX_MAGIC,
    MAX_TEXT_CHARS,
    MAX_URL_LENGTH,
    MAX_WEB_BYTES,
    PDF_MAGIC,
    WEB_MAX_REDIRECTS,
    WEB_TIMEOUT_SEC,
)
from callbot_platform.knowledge.repos import KnowledgeError
from callbot_platform.knowledge.ssrf import (
    assert_resolved_public,
    validate_public_http_url,
)

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")


@dataclass(slots=True)
class ExtractedDocument:
    title: str
    text: str
    language: str = "en"
    source_type: str = "TEXT"
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_text(text: str) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "".join(ch if ch == "\n" or ord(ch) >= 32 or ch == "\t" else " " for ch in cleaned)
    cleaned = _WS_RE.sub(" ", cleaned)
    cleaned = _BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()[:MAX_TEXT_CHARS]


class TextExtractor:
    def extract(self, data: bytes, *, filename: str | None = None) -> ExtractedDocument:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        title = (filename or "text").rsplit(".", 1)[0][:255]
        return ExtractedDocument(
            title=title, text=normalize_text(text), source_type="TEXT"
        )


class PdfExtractor:
    def extract(self, data: bytes, *, filename: str | None = None) -> ExtractedDocument:
        if not data.startswith(PDF_MAGIC):
            raise KnowledgeError("invalid_document", "File is not a valid PDF")
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise KnowledgeError(
                "extractor_unavailable", "PDF extractor not installed"
            ) from exc
        try:
            reader = PdfReader(io.BytesIO(data))
            parts: list[str] = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    parts.append(f"[Page {i + 1}]\n{page_text}")
            meta_title = None
            if reader.metadata:
                meta_title = getattr(reader.metadata, "title", None) or None
            title = (meta_title or filename or "pdf").strip()[:255] or "pdf"
            text = normalize_text("\n\n".join(parts))
            if not text:
                raise KnowledgeError("invalid_document", "PDF contained no extractable text")
            return ExtractedDocument(
                title=title,
                text=text,
                source_type="PDF",
                metadata={"page_count": len(reader.pages)},
            )
        except KnowledgeError:
            raise
        except Exception as exc:
            logger.warning("pdf_extract_failed err=%s", type(exc).__name__)
            raise KnowledgeError("invalid_document", "Unable to extract PDF text") from exc


class DocxExtractor:
    def extract(self, data: bytes, *, filename: str | None = None) -> ExtractedDocument:
        if not data.startswith(DOCX_MAGIC):
            raise KnowledgeError("invalid_document", "File is not a valid DOCX")
        try:
            from docx import Document
        except ImportError as exc:
            raise KnowledgeError(
                "extractor_unavailable", "DOCX extractor not installed"
            ) from exc
        try:
            doc = Document(io.BytesIO(data))
            parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
            text = normalize_text("\n\n".join(parts))
            if not text:
                raise KnowledgeError("invalid_document", "DOCX contained no extractable text")
            title = (filename or "document").rsplit(".", 1)[0][:255]
            return ExtractedDocument(title=title, text=text, source_type="DOCX")
        except KnowledgeError:
            raise
        except Exception as exc:
            logger.warning("docx_extract_failed err=%s", type(exc).__name__)
            raise KnowledgeError("invalid_document", "Unable to extract DOCX text") from exc


class WebExtractor:
    def extract_url(self, url: str) -> ExtractedDocument:
        safe = validate_public_http_url(url, max_length=MAX_URL_LENGTH)
        host = urlparse(safe).hostname or ""
        assert_resolved_public(host)
        try:
            with httpx.Client(
                timeout=WEB_TIMEOUT_SEC,
                follow_redirects=False,
            ) as client:
                current = safe
                for _ in range(WEB_MAX_REDIRECTS + 1):
                    parsed = urlparse(current)
                    assert_resolved_public(parsed.hostname or "")
                    resp = client.get(current)
                    if resp.status_code in {301, 302, 303, 307, 308}:
                        loc = resp.headers.get("location")
                        if not loc:
                            raise KnowledgeError("invalid_url", "Redirect without Location")
                        if loc.startswith("/"):
                            current = f"{parsed.scheme}://{parsed.netloc}{loc}"
                        else:
                            current = validate_public_http_url(loc, max_length=MAX_URL_LENGTH)
                        continue
                    if resp.status_code >= 400:
                        raise KnowledgeError(
                            "fetch_failed", f"Website returned HTTP {resp.status_code}"
                        )
                    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                    if ctype and "html" not in ctype and "text" not in ctype:
                        raise KnowledgeError(
                            "invalid_document", f"Unsupported content type: {ctype}"
                        )
                    body = resp.content[: MAX_WEB_BYTES + 1]
                    if len(body) > MAX_WEB_BYTES:
                        raise KnowledgeError("invalid_document", "Website response too large")
                    html = body.decode("utf-8", errors="replace")
                    title, text = _html_to_text(html)
                    if not text:
                        raise KnowledgeError("invalid_document", "Website had no extractable text")
                    return ExtractedDocument(
                        title=title or (parsed.hostname or "website")[:255],
                        text=normalize_text(text),
                        source_type="WEBSITE",
                        metadata={"url": current},
                    )
                raise KnowledgeError("invalid_url", "Too many redirects")
        except KnowledgeError:
            raise
        except httpx.TimeoutException as exc:
            raise KnowledgeError("provider_timeout", "Website fetch timed out") from exc
        except Exception as exc:
            logger.warning("web_extract_failed err=%s", type(exc).__name__)
            raise KnowledgeError("fetch_failed", "Unable to fetch website") from exc


def _html_to_text(html: str) -> tuple[str, str]:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
    # Strip scripts/styles then tags.
    cleaned = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p>", "\n\n", cleaned)
    cleaned = re.sub(r"(?i)</h[1-6]>", "\n\n", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"&amp;", "&", cleaned)
    cleaned = re.sub(r"&lt;", "<", cleaned)
    cleaned = re.sub(r"&gt;", ">", cleaned)
    return title[:255], cleaned


class DocumentExtractor:
    def __init__(self) -> None:
        self._text = TextExtractor()
        self._pdf = PdfExtractor()
        self._docx = DocxExtractor()
        self._web = WebExtractor()

    def extract_bytes(
        self, data: bytes, *, source_type: str, filename: str | None = None
    ) -> ExtractedDocument:
        st = source_type.upper()
        if st == "PDF":
            return self._pdf.extract(data, filename=filename)
        if st == "DOCX":
            return self._docx.extract(data, filename=filename)
        return self._text.extract(data, filename=filename)

    def extract_text(self, text: str, *, source_type: str, title: str) -> ExtractedDocument:
        return ExtractedDocument(
            title=title[:255],
            text=normalize_text(text),
            source_type=source_type.upper(),
        )

    def extract_url(self, url: str) -> ExtractedDocument:
        return self._web.extract_url(url)
