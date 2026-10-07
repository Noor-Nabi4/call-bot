"""Knowledge base APIs: internal search for voice + ops CRUD + Phase 16 sources."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_permission,
    require_internal_token,
)
from callbot_platform.knowledge.repos import KnowledgeError, KnowledgeRepository
from callbot_platform.knowledge.retrieval import KnowledgeRetrievalService
from callbot_platform.knowledge.sources import KnowledgeSourceService
from callbot_platform.rbac.ai_auth import require_ai_tool_permission
from callbot_platform.security.call_scope import (
    CallScope,
    enforce_body_tenant,
    optional_or_required_call_scope,
)

internal_router = APIRouter(
    prefix="/internal/knowledge",
    dependencies=[Depends(require_internal_token)],
    tags=["knowledge-internal"],
)

ops_router = APIRouter(prefix="/api/knowledge", tags=["knowledge-ops"])

_require_knowledge_read = require_entitled_permission("knowledge.read")
_require_knowledge_manage = require_entitled_permission("knowledge.manage")


class SearchBody(BaseModel):
    tenant_id: UUID
    query: str
    limit: int = Field(default=5, ge=1, le=10)
    agent_profile_id: UUID | None = None


class OpsSearchBody(BaseModel):
    model_config = {"extra": "forbid"}

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)
    agent_profile_id: UUID | None = None


class ArticleBody(BaseModel):
    title: str
    body: str
    category: str = "faq"
    tags: list[str] = Field(default_factory=list)
    is_active: bool | None = None
    agent_profile_id: UUID | None = None


class TextSourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)
    source_type: str = Field(default="TEXT", alias="sourceType")
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    product_id: UUID | None = Field(default=None, alias="productId")
    sync: bool = False


class WebsiteSourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    sync: bool = False


class SemanticSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20, alias="topK")
    source_type: str | None = Field(default=None, alias="sourceType")
    category: str | None = None


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, KnowledgeError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "plan_limit_exceeded":
            status = 403
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@internal_router.post("/search")
def internal_search(
    body: SearchBody,
    session: Session = Depends(db_dep),  # noqa: B008
    scope: CallScope | None = Depends(optional_or_required_call_scope),  # noqa: B008
) -> dict[str, Any]:
    if scope is not None:
        enforce_body_tenant(scope, body.tenant_id)
    require_ai_tool_permission(session, body.tenant_id, "knowledge")
    try:
        # Hybrid: RAG chunks + legacy curated articles.
        result = KnowledgeRetrievalService(session).retrieve(
            body.tenant_id,
            body.query,
            top_k=body.limit,
            channel="voice",
            include_legacy_articles=True,
        )
        # Backward-compatible article shape for existing voice client.
        articles = []
        for r in result.get("results") or []:
            articles.append(
                {
                    "id": r.get("chunk_id") or r.get("source_id"),
                    "title": r.get("source_title"),
                    "body": r.get("content"),
                    "category": (r.get("metadata") or {}).get("category") or "knowledge",
                    "score": r.get("score"),
                    "untrusted": True,
                    "usage": (r.get("metadata") or {}).get("usage"),
                    "source_type": r.get("source_type"),
                }
            )
        return {
            "articles": articles,
            "count": len(articles),
            "status": result.get("status"),
        }
    except Exception as exc:
        raise _http(exc) from exc


@ops_router.get("")
def list_articles(
    limit: int = 200,
    offset: int = 0,
    user: CurrentUser = Depends(_require_knowledge_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "articles": KnowledgeRepository(session).list(
            user.tenant_id, limit=limit, offset=offset
        )
    }


@ops_router.post("/search")
def ops_search(
    body: OpsSearchBody,
    user: CurrentUser = Depends(_require_knowledge_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    """Preview the same ranked search the voice agent uses (session-scoped)."""
    try:
        hits = KnowledgeRepository(session).search(
            user.tenant_id,
            body.query,
            limit=body.limit,
            agent_profile_id=body.agent_profile_id,
        )
        return {"articles": hits, "count": len(hits)}
    except Exception as exc:
        raise _http(exc) from exc


@ops_router.post("")
def create_article(
    body: ArticleBody,
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        article = KnowledgeRepository(session).create(
            user.tenant_id,
            title=body.title,
            body=body.body,
            category=body.category,
            tags=body.tags,
            agent_profile_id=body.agent_profile_id,
            actor=user.email,
        )
        return {"article": article}
    except Exception as exc:
        raise _http(exc) from exc


@ops_router.put("/{article_id}")
def update_article(
    article_id: UUID,
    body: ArticleBody,
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        article = KnowledgeRepository(session).update(
            user.tenant_id,
            article_id,
            title=body.title,
            body=body.body,
            category=body.category,
            tags=body.tags,
            is_active=body.is_active,
            agent_profile_id=body.agent_profile_id,
            actor=user.email,
        )
        return {"article": article}
    except Exception as exc:
        raise _http(exc) from exc


@ops_router.delete("/{article_id}")
def delete_article(
    article_id: UUID,
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, bool]:
    try:
        KnowledgeRepository(session).delete(
            user.tenant_id, article_id, actor=user.email
        )
        return {"ok": True}
    except Exception as exc:
        raise _http(exc) from exc


# --- Phase 16 knowledge sources ---


@ops_router.get("/sources")
def list_sources(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    source_type: str | None = None,
    user: CurrentUser = Depends(_require_knowledge_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "sources": KnowledgeSourceService(session).list(
            user.tenant_id,
            limit=limit,
            offset=offset,
            status=status,
            source_type=source_type,
        )
    }


@ops_router.get("/sources/{source_id}")
def get_source(
    source_id: UUID,
    user: CurrentUser = Depends(_require_knowledge_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"source": KnowledgeSourceService(session).get(user.tenant_id, source_id)}
    except Exception as exc:
        raise _http(exc) from exc


@ops_router.get("/sources/{source_id}/status")
def source_status(
    source_id: UUID,
    user: CurrentUser = Depends(_require_knowledge_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        src = KnowledgeSourceService(session).get(user.tenant_id, source_id)
        return {
            "id": src["id"],
            "status": src["status"],
            "version": src["version"],
            "active_version": src["active_version"],
            "chunk_count": src["chunk_count"],
            "failure_code": src["failure_code"],
            "failure_message": src["failure_message"],
            "last_indexed_at": src["last_indexed_at"],
        }
    except Exception as exc:
        raise _http(exc) from exc


@ops_router.post("/sources/text")
def create_text_source(
    body: TextSourceBody,
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        source = KnowledgeSourceService(session).create_text(
            user.tenant_id,
            name=body.name,
            text=body.text,
            source_type=body.source_type,
            description=body.description,
            metadata=body.metadata,
            product_id=body.product_id,
            actor=user.email,
            sync=body.sync,
        )
        session.commit()
        return {"source": source}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@ops_router.post("/sources/website")
def create_website_source(
    body: WebsiteSourceBody,
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        source = KnowledgeSourceService(session).create_website(
            user.tenant_id,
            name=body.name,
            url=body.url,
            description=body.description,
            metadata=body.metadata,
            actor=user.email,
            sync=body.sync,
        )
        session.commit()
        return {"source": source}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@ops_router.post("/sources/upload")
async def upload_source(
    name: str = Form(...),
    source_type: str = Form(...),
    description: str | None = Form(default=None),
    sync: bool = Form(default=False),
    file: UploadFile = File(...),  # noqa: B008
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = await file.read()
        source = KnowledgeSourceService(session).create_upload(
            user.tenant_id,
            name=name,
            filename=file.filename or "upload.bin",
            data=data,
            source_type=source_type,
            description=description,
            actor=user.email,
            sync=sync,
        )
        session.commit()
        return {"source": source}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@ops_router.post("/sources/{source_id}/reindex")
def reindex_source(
    source_id: UUID,
    sync: bool = False,
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        source = KnowledgeSourceService(session).reindex(
            user.tenant_id, source_id, actor=user.email, sync=sync
        )
        session.commit()
        return {"source": source}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@ops_router.delete("/sources/{source_id}")
def delete_source(
    source_id: UUID,
    user: CurrentUser = Depends(_require_knowledge_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, bool]:
    try:
        KnowledgeSourceService(session).delete(
            user.tenant_id, source_id, actor=user.email
        )
        session.commit()
        return {"ok": True}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@ops_router.post("/semantic-search")
def semantic_search(
    body: SemanticSearchBody,
    user: CurrentUser = Depends(_require_knowledge_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        filters: dict[str, Any] = {}
        if body.source_type:
            filters["source_type"] = body.source_type
        if body.category:
            filters["category"] = body.category
        return KnowledgeRetrievalService(session).retrieve(
            user.tenant_id,
            body.query,
            top_k=body.top_k,
            filters=filters,
            channel="ops",
        )
    except Exception as exc:
        raise _http(exc) from exc
