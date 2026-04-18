"""
/api/v1/content — 内容条目的增删改查 + 搜索路由。
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api_server.middleware.cache import cached_response
from api_server.schemas import (
    ContentBundleResponse,
    ContentItemDetail,
    ContentListResponse,
    ContentSearchResponse,
    MarkUsedRequest,
    PageMeta,
    SemanticSearchRequest,
    SemanticSearchResponse,
    ContentItemSummary,
    TrendingTopic,
    TrendingTopicsResponse,
)
from knowledge_base.repository import ContentRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/content", tags=["content"])
_repo = ContentRepository()


# ── 辅助函数 ──────────────────────────────────────────────────────

def _to_summary(row: dict) -> ContentItemSummary:
    return ContentItemSummary(
        id=row["id"],
        content_type=row["content_type"],
        title=row["title"],
        source_platform=row["source_platform"],
        source_url=row.get("source_url"),
        published_at=row.get("published_at"),
        summary=row.get("summary"),
        thumbnail_url=row.get("thumbnail_url"),
        media_url=row.get("media_url"),
        duration_sec=row.get("duration_sec"),
        importance_score=row.get("importance_score", 0.0),
        tags=row.get("tags") or [],
        category=row.get("category"),
        date_partition=row.get("date_partition"),
    )


# ── 路由 ───────────────────────────────────────────────────────

@router.get("", response_model=ContentListResponse)
@cached_response(ttl=300, prefix="content_list")
async def list_content(
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    content_type: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[int] = Query(None, description="Pagination cursor (last seen id)"),
):
    """
    列出内容条目，支持可选过滤条件。
    使用游标分页以提升性能。
    """
    from datetime import date as date_cls
    date_str = date or date_cls.today().isoformat()

    rows = await _repo.list_by_date(
        date_str,
        content_type=content_type,
        platform=platform,
        limit=limit + 1,
        cursor_id=cursor,
    )

    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1]["id"]
        rows = rows[:limit]

    return ContentListResponse(
        items=[_to_summary(r) for r in rows],
        meta=PageMeta(limit=limit, next_cursor=next_cursor),
    )


@router.get("/search", response_model=ContentSearchResponse)
@cached_response(ttl=300, prefix="content_search")
async def search_content(
    q: str = Query(..., min_length=1, max_length=200),
    content_type: Optional[str] = Query(None),
    limit: int = Query(default=20, ge=1, le=50),
):
    """基于 pg_trgm 的全文三元组相似度搜索，匹配标题和正文。"""
    rows = await _repo.search_fulltext(q, content_type=content_type, limit=limit)
    return ContentSearchResponse(
        items=[_to_summary(r) for r in rows],
        query=q,
        total=len(rows),
    )


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(body: SemanticSearchRequest):
    """
    语义向量搜索。服务端实时对查询文本进行向量嵌入。
    需要在配置中启用嵌入功能（应用启动时初始化 BatchEmbedder）。
    """
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

    rows = await _repo.search_semantic(
        vec,
        content_type=body.content_type,
        date_from=body.date_from,
        limit=body.limit,
    )
    return SemanticSearchResponse(items=[_to_summary(r) for r in rows], query=body.query)


@router.get("/trending", response_model=ContentListResponse)
@cached_response(ttl=300, prefix="trending")
async def get_trending(
    date: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """获取指定日期的热门内容，按重要性分数排序。"""
    from datetime import date as date_cls
    date_str = date or date_cls.today().isoformat()
    rows = await _repo.get_trending(date_str, content_type=content_type, limit=limit)
    return ContentListResponse(
        items=[_to_summary(r) for r in rows],
        meta=PageMeta(limit=limit),
    )


@router.get("/topics/trending", response_model=TrendingTopicsResponse)
@cached_response(ttl=300, prefix="topics_trending")
async def get_trending_topics(
    date: Optional[str] = Query(None),
    days: int = Query(default=1, ge=1, le=7),
    limit: int = Query(default=10, ge=1, le=20),
):
    """按分类聚合的热门主题，含数量、来源数、平均重要性。"""
    from datetime import date as date_cls
    date_str = date or date_cls.today().isoformat()
    rows = await _repo.get_trending_topics(date_str, days=days, limit=limit)
    topics = []
    for r in rows:
        top_tags = r.get("top_tags") or []
        if isinstance(top_tags, list):
            top_tags = top_tags[:10]
        topics.append(TrendingTopic(
            category=r["category"],
            count=r["count"],
            sources=r["sources"],
            avg_importance=round(float(r["avg_importance"] or 0), 2),
            top_tags=top_tags,
        ))
    return TrendingTopicsResponse(date=date_str, topics=topics)


@router.get("/bundle", response_model=ContentBundleResponse)
@cached_response(ttl=300, prefix="content_bundle")
async def get_content_bundle(
    category: str = Query(..., min_length=1),
    date: Optional[str] = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取某主题分类下的素材包。"""
    from datetime import date as date_cls
    date_str = date or date_cls.today().isoformat()
    rows = await _repo.list_by_category(date_str, category=category, limit=limit)
    return ContentBundleResponse(
        category=category,
        items=[_to_summary(r) for r in rows],
        total=len(rows),
    )


@router.post("/{content_id}/mark_used")
async def mark_content_used(content_id: int, body: MarkUsedRequest):
    """标记素材已被某人设使用。"""
    row = await _repo.get_by_id(content_id)
    if not row:
        raise HTTPException(status_code=404, detail="Content item not found.")
    await _repo.mark_used(content_id, body.persona_id)
    return {"ok": True, "content_id": content_id, "persona_id": body.persona_id}


@router.get("/{content_id}", response_model=ContentItemDetail)
@cached_response(ttl=1800, prefix="content_detail")
async def get_content(content_id: int):
    """根据 ID 获取单个内容条目，包含完整正文和图片。"""
    row = await _repo.get_by_id(content_id)
    if not row:
        raise HTTPException(status_code=404, detail="Content item not found.")
    return ContentItemDetail(
        id=row["id"],
        content_type=row["content_type"],
        title=row["title"],
        source_platform=row["source_platform"],
        source_url=row.get("source_url"),
        published_at=row.get("published_at"),
        summary=row.get("summary"),
        full_text=row.get("full_text"),
        thumbnail_url=row.get("thumbnail_url"),
        media_url=row.get("media_url"),
        duration_sec=row.get("duration_sec"),
        image_urls=row.get("image_urls") or [],
        importance_score=row.get("importance_score", 0.0),
        tags=row.get("tags") or [],
        category=row.get("category"),
        date_partition=row.get("date_partition"),
        raw_metadata=row.get("raw_metadata") or {},
    )
