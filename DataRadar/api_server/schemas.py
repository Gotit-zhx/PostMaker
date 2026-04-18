"""
知识库 API 的 Pydantic 响应模型定义。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ================================================================
# 通用模型
# ================================================================

class PageMeta(BaseModel):
    """分页元数据。"""
    limit: int
    next_cursor: Optional[int] = None


# ================================================================
# 内容条目
# ================================================================

class ContentItemSummary(BaseModel):
    """轻量级内容条目，用于列表响应。"""
    id: int
    content_type: str
    title: str
    source_platform: str
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_url: Optional[str] = None
    duration_sec: Optional[int] = None
    importance_score: float
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    date_partition: Optional[date] = None

    class Config:
        from_attributes = True


class ContentItemDetail(ContentItemSummary):
    """完整内容条目，包含正文和图片。"""
    full_text: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)


class ContentListResponse(BaseModel):
    items: List[ContentItemSummary]
    meta: PageMeta


class ContentSearchResponse(BaseModel):
    items: List[ContentItemSummary]
    query: str
    total: int


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    content_type: Optional[str] = None
    date_from: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class SemanticSearchResponse(BaseModel):
    items: List[ContentItemSummary]
    query: str


# ================================================================
# 知识条目
# ================================================================

class SourceLink(BaseModel):
    """关联到知识条目的内容来源。"""
    id: int
    title: str
    source_platform: str
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None


class KnowledgeEntrySummary(BaseModel):
    id: int
    canonical_title: str
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    importance_score: float
    source_count: int
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class KnowledgeEntryDetail(KnowledgeEntrySummary):
    full_text: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)
    sources: List[SourceLink] = Field(default_factory=list)


class KnowledgeListResponse(BaseModel):
    items: List[KnowledgeEntrySummary]
    meta: PageMeta


class KnowledgeSemanticRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class KnowledgeSemanticResponse(BaseModel):
    items: List[KnowledgeEntrySummary]
    query: str


# ================================================================
# 统计
# ================================================================

class StatsOverview(BaseModel):
    total_items: int
    by_type: Dict[str, int]
    by_platform: Dict[str, int]
    latest_date: Optional[str] = None


class TrendingResponse(BaseModel):
    date: str
    items: List[ContentItemSummary]


class TrendingTopic(BaseModel):
    category: str
    count: int
    sources: int
    avg_importance: float
    top_tags: List[str] = Field(default_factory=list)


class TrendingTopicsResponse(BaseModel):
    date: str
    topics: List[TrendingTopic]


class ContentBundleResponse(BaseModel):
    category: str
    items: List[ContentItemSummary]
    total: int


class MarkUsedRequest(BaseModel):
    persona_id: str = Field(..., min_length=1, max_length=100)
