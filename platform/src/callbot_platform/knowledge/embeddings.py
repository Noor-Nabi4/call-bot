"""Embedding service abstraction — OpenAI + deterministic fake for tests."""

from __future__ import annotations

import hashlib
import logging
import math
import random
from abc import ABC, abstractmethod
from collections.abc import Sequence

import httpx

from callbot_platform.config import Settings, get_settings
from callbot_platform.knowledge.constants import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_VERSION,
)
from callbot_platform.knowledge.repos import KnowledgeError

logger = logging.getLogger(__name__)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def normalize_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class EmbeddingService(ABC):
    model: str
    dimension: int
    version: str

    @abstractmethod
    def generate(self, text: str) -> list[float]: ...

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.generate(t) for t in texts]


class FakeEmbeddingService(EmbeddingService):
    """Deterministic embeddings for offline/tests — same text ⇒ same vector."""

    def __init__(
        self,
        *,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        model: str = "fake-embedding",
        version: str = DEFAULT_EMBEDDING_VERSION,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self.version = version

    def generate(self, text: str) -> list[float]:
        # Bag-of-tokens hashing: shared vocabulary ⇒ high cosine (test-friendly).
        import re

        tokens = re.findall(r"[a-z0-9]{2,}", (text or "").lower())
        vec = [0.0] * self.dimension
        if not tokens:
            digest = hashlib.sha256((text or "").encode()).digest()
            rng = random.Random(int.from_bytes(digest[:8], "big"))
            return normalize_vector([rng.gauss(0, 1) for _ in range(self.dimension)])
        for tok in tokens:
            td = hashlib.sha256(tok.encode()).digest()
            # Map token into a few dimensions deterministically.
            for n in range(4):
                idx = int.from_bytes(td[n * 2 : n * 2 + 2], "big") % self.dimension
                sign = 1.0 if td[8 + n] % 2 == 0 else -1.0
                vec[idx] += sign
        return normalize_vector(vec)


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        version: str = DEFAULT_EMBEDDING_VERSION,
        timeout_sec: float = 30.0,
    ) -> None:
        if not api_key:
            raise KnowledgeError("provider_unavailable", "OPENAI_API_KEY is not configured")
        self._api_key = api_key
        self.model = model
        self.dimension = dimension
        self.version = version
        self._timeout = timeout_sec

    def generate(self, text: str) -> list[float]:
        return self.generate_batch([text])[0]

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        cleaned = [(t or "").strip()[:8000] for t in texts]
        if not cleaned:
            return []
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": cleaned,
                        "dimensions": self.dimension,
                    },
                )
        except httpx.TimeoutException as exc:
            raise KnowledgeError("provider_timeout", "Embedding provider timed out") from exc
        except Exception as exc:
            logger.exception("embedding_request_failed")
            raise KnowledgeError("provider_error", "Embedding provider request failed") from exc

        if resp.status_code == 429:
            raise KnowledgeError("rate_limited", "Embedding provider rate limited")
        if resp.status_code >= 500:
            raise KnowledgeError("provider_error", "Embedding provider unavailable")
        if resp.status_code >= 400:
            raise KnowledgeError("provider_error", "Embedding provider rejected request")
        try:
            payload = resp.json()
            rows = sorted(payload.get("data") or [], key=lambda r: int(r.get("index") or 0))
            out: list[list[float]] = []
            for row in rows:
                vec = row.get("embedding")
                if not isinstance(vec, list) or len(vec) != self.dimension:
                    raise KnowledgeError(
                        "invalid_embedding", "Embedding dimension mismatch"
                    )
                out.append([float(x) for x in vec])
            if len(out) != len(cleaned):
                raise KnowledgeError("invalid_embedding", "Incomplete embedding batch")
            return out
        except KnowledgeError:
            raise
        except Exception as exc:
            raise KnowledgeError("invalid_embedding", "Malformed embedding response") from exc


def get_embedding_service(settings: Settings | None = None) -> EmbeddingService:
    cfg = settings or get_settings()
    api_key = getattr(cfg, "openai_api_key", "") or ""
    model = getattr(cfg, "knowledge_embedding_model", None) or DEFAULT_EMBEDDING_MODEL
    dim = int(
        getattr(cfg, "knowledge_embedding_dimension", None) or DEFAULT_EMBEDDING_DIMENSION
    )
    version = (
        getattr(cfg, "knowledge_embedding_version", None) or DEFAULT_EMBEDDING_VERSION
    )
    if api_key:
        return OpenAIEmbeddingService(
            api_key=api_key, model=model, dimension=dim, version=version
        )
    # Dev/test fallback — never used for production provider verification claims.
    return FakeEmbeddingService(dimension=dim, model=f"fake:{model}", version=version)
