"""Knowledge base APIs: internal search for voice + ops CRUD."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_ops_roles,
    require_internal_token,
)
from callbot_platform.knowledge.repos import KnowledgeError, KnowledgeRepository
from callbot_platform.security.session import ROLE_ADMIN, ROLE_DISPATCHER

internal_router = APIRouter(
    prefix="/internal/knowledge",
    dependencies=[Depends(require_internal_token)],
    tags=["knowledge-internal"],
)

ops_router = APIRouter(prefix="/api/knowledge", tags=["knowledge-ops"])


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
    body: SearchBody, session: Session = Depends(db_dep)
) -> dict[str, Any]:
    try:
        hits = KnowledgeRepository(session).search(
            body.tenant_id,
            body.query,
            limit=body.limit,
            agent_profile_id=body.agent_profile_id,
        )
        return {"articles": hits, "count": len(hits)}
    except Exception as exc:
        raise _http(exc) from exc


@ops_router.get("")
def list_articles(
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"articles": KnowledgeRepository(session).list(user.tenant_id)}


@ops_router.post("/search")
def ops_search(
    body: OpsSearchBody,
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
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
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
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
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
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
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
) -> dict[str, bool]:
    try:
        KnowledgeRepository(session).delete(
            user.tenant_id, article_id, actor=user.email
        )
        return {"ok": True}
    except Exception as exc:
        raise _http(exc) from exc
