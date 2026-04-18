"""
/api/v1/knowledge — 知识条目的增删改查 + 语义搜索路由。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api_server.middleware.cache import cached_response
from api_server.schemas import (
    KnowledgeEntryDetail,
    KnowledgeEntrySummary,
    KnowledgeListResponse,
    KnowledgeSemanticRequest,
    KnowledgeSemanticResponse,
    PageMeta,
    SourceLink,
)
from knowledge_base.repository import KnowledgeRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
_repo = KnowledgeRepository()


def _to_summary(row: dict) -> KnowledgeEntrySummary:
    return KnowledgeEntrySummary(
        id=row["id"],
        canonical_title=row["canonical_title"],
        summary=row.get("summary"),
        category=row.get("category"),
        tags=row.get("tags") or [],
        importance_score=row.get("importance_score", 0.0),
        source_count=row.get("source_count", 1),
        first_seen_at=row.get("first_seen_at"),
        last_seen_at=row.get("last_seen_at"),
    )


@router.get("", response_model=KnowledgeListResponse)
@cached_response(ttl=300, prefix="knowledge_list")
async def list_knowledge(
    days: int = Query(default=7, ge=1, le=90, description="Recent N days"),
    category: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[int] = Query(None),
):
    """列出近期知识条目，按重要性分数排序。"""
    rows = await _repo.list_recent(
        days=days,
        category=category,
        limit=limit + 1,
        cursor_id=cursor,
    )

    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1]["id"]
        rows = rows[:limit]

    return KnowledgeListResponse(
        items=[_to_summary(r) for r in rows],
        meta=PageMeta(limit=limit, next_cursor=next_cursor),
    )


@router.post("/semantic", response_model=KnowledgeSemanticResponse)
async def semantic_search(body: KnowledgeSemanticRequest):
    """基于 pgvector 对知识条目进行语义搜索。"""
    from api_server.main import get_embedder

    embedder = get_embedder()
    if not embedder:
        raise HTTPException(
            status_code=503,
            detail="Semantic search is disabled (no embedder configured).",
        )

    vec = await embedder.embed_single(body.query)
    if not vec:
        raise HTTPException(status_code=502, detail="Embedding generation failed.")

    rows = await _repo.search_semantic(vec, limit=body.limit, category=body.category)
    return KnowledgeSemanticResponse(
        items=[_to_summary(r) for r in rows],
        query=body.query,
    )


@router.get("/{entry_id}", response_model=KnowledgeEntryDetail)
@cached_response(ttl=1800, prefix="knowledge_detail")
async def get_knowledge_entry(entry_id: int):
    """根据 ID 获取单个知识条目，包含关联的来源文章。"""
    row = await _repo.get_by_id(entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")

    sources = [
        SourceLink(
            id=s["id"],
            title=s["title"],
            source_platform=s["source_platform"],
            source_url=s.get("source_url"),
            published_at=s.get("published_at"),
        )
        for s in (row.get("sources") or [])
    ]

    return KnowledgeEntryDetail(
        id=row["id"],
        canonical_title=row["canonical_title"],
        summary=row.get("summary"),
        full_text=row.get("full_text"),
        category=row.get("category"),
        tags=row.get("tags") or [],
        image_urls=row.get("image_urls") or [],
        importance_score=row.get("importance_score", 0.0),
        source_count=row.get("source_count", 1),
        first_seen_at=row.get("first_seen_at"),
        last_seen_at=row.get("last_seen_at"),
        sources=sources,
    )
