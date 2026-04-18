"""
/api/v1/stats — 统计数据和热门趋势路由。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from api_server.middleware.cache import cached_response
from api_server.schemas import StatsOverview, TrendingResponse, ContentItemSummary
from knowledge_base.repository import ContentRepository

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])
_repo = ContentRepository()


@router.get("/overview", response_model=StatsOverview)
@cached_response(ttl=600, prefix="stats_overview")
async def get_overview():
    """知识库整体统计概览（缓存 10 分钟）。"""
    stats = await _repo.get_stats()
    return StatsOverview(
        total_items=stats["total_items"],
        by_type=stats["by_type"],
        by_platform=stats["by_platform"],
        latest_date=stats.get("latest_date"),
    )


@router.get("/trending", response_model=TrendingResponse)
@cached_response(ttl=300, prefix="stats_trending")
async def get_trending(
    date_str: str = Query(
        default=None,
        alias="date",
        description="YYYY-MM-DD. Defaults to today.",
    ),
    content_type: str = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """获取指定日期的热门内容排行。"""
    target_date = date_str or date.today().isoformat()
    rows = await _repo.get_trending(target_date, content_type=content_type, limit=limit)
    items = [
        ContentItemSummary(
            id=r["id"],
            content_type=r["content_type"],
            title=r["title"],
            source_platform=r["source_platform"],
            source_url=r.get("source_url"),
            published_at=r.get("published_at"),
            summary=r.get("summary"),
            thumbnail_url=r.get("thumbnail_url"),
            media_url=r.get("media_url"),
            duration_sec=r.get("duration_sec"),
            importance_score=r.get("importance_score", 0.0),
            tags=r.get("tags") or [],
            category=r.get("category"),
            date_partition=r.get("date_partition"),
        )
        for r in rows
    ]
    return TrendingResponse(date=target_date, items=items)
