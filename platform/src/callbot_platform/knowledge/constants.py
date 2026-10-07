"""Phase 16 knowledge / RAG constants."""

from __future__ import annotations

SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "PDF",
        "DOCX",
        "WEBSITE",
        "TEXT",
        "FAQ",
        "POLICY",
        "BUSINESS_INFORMATION",
        "PRODUCT_DESCRIPTION",
    }
)

SOURCE_STATUSES: frozenset[str] = frozenset(
    {"ACTIVE", "PROCESSING", "FAILED", "ARCHIVED", "DELETED"}
)

# Chunking: character-based with paragraph preference.
# ~800 chars ~= 150-200 tokens for English prose; keeps SMS/voice context tight.
CHUNK_TARGET_CHARS = 800
CHUNK_MAX_CHARS = 1200
CHUNK_OVERLAP_CHARS = 100

DEFAULT_TOP_K = 5
MAX_TOP_K = 20
MAX_CONTEXT_CHARS = 6000
MAX_CHUNKS_PER_SOURCE = 3

# Cosine similarity threshold (tuned via FakeEmbedding/OpenAI local tests).
DEFAULT_RELEVANCE_THRESHOLD = 0.35

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSION = 1536
DEFAULT_EMBEDDING_VERSION = "v1"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_TEXT_CHARS = 500_000
MAX_URL_LENGTH = 2048
MAX_WEB_BYTES = 2 * 1024 * 1024
WEB_TIMEOUT_SEC = 10.0
WEB_MAX_REDIRECTS = 3

ALLOWED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "category",
        "language",
        "title",
        "tags",
        "policy_type",
        "section",
        "product_id",
    }
)
MAX_METADATA_KEY_LEN = 64
MAX_METADATA_VALUE_LEN = 256
MAX_METADATA_TAGS = 20
MAX_METADATA_JSON_BYTES = 4096

PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK"  # zip container

ALLOWED_UPLOAD_MIME: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    }
)
