"""
知识库的数据库 CRUD 操作。

两个主要仓储类：
- ContentRepository:   content_items 表（原始采集数据）
- KnowledgeRepository: knowledge_entries 表（聚合去重后的数据）

所有方法均为异步，使用全局 asyncpg 连接池（db.get_pool()）。
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from knowledge_base.db import get_pool

logger = logging.getLogger(__name__)


# ================================================================
# 数据模型
# ================================================================

@dataclass
class ContentItemInput:
    """插入/更新内容条目的输入模型。"""
    content_type: str               # text | video | audio | image
    title: str
    source_platform: str
    source_url: str
    date_partition: str             # YYYY-MM-DD

    published_at: Optional[str] = None
    summary: Optional[str] = None
    full_text: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_url: Optional[str] = None
    duration_sec: Optional[int] = None
    image_urls: List[str] = field(default_factory=list)
    importance_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class KnowledgeEntryInput:
    """插入/更新知识条目的输入模型。"""
    canonical_title: str
    first_seen_at: str              # ISO-8601
    last_seen_at: str

    summary: Optional[str] = None
    full_text: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    image_urls: List[str] = field(default_factory=list)
    importance_score: float = 0.0
    embedding: Optional[List[float]] = None
    source_count: int = 1


# ================================================================
# ContentRepository
# ================================================================

class ContentRepository:
    """content_items 表的 CRUD 操作。"""

    async def upsert(self, item: ContentItemInput) -> int:
        """
        插入或更新一条内容条目。
        返回插入/更新行的 id。
        """
        pool = get_pool()
        content_hash = _make_hash(item.source_platform, item.source_url)
        # asyncpg 要求使用原生 Python date/datetime 对象，而非字符串
        date_val = item.date_partition
        if isinstance(date_val, str):
            date_val = date.fromisoformat(date_val)
        published_val = item.published_at
        if isinstance(published_val, str) and published_val:
            published_val = datetime.fromisoformat(published_val)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO content_items (
                    content_type, title, source_platform, source_url,
                    date_partition, published_at, summary, full_text,
                    thumbnail_url, media_url, duration_sec, image_urls,
                    importance_score, tags, category, raw_metadata,
                    embedding, content_hash
                ) VALUES (
                    $1, $2, $3, $4,
                    $5, $6::timestamptz, $7, $8,
                    $9, $10, $11, $12,
                    $13, $14, $15, $16::jsonb,
                    $17::vector, $18
                )
                ON CONFLICT (source_platform, source_url) DO UPDATE SET
                    title           = EXCLUDED.title,
                    summary         = COALESCE(EXCLUDED.summary, content_items.summary),
                    full_text       = COALESCE(EXCLUDED.full_text, content_items.full_text),
                    thumbnail_url   = COALESCE(EXCLUDED.thumbnail_url, content_items.thumbnail_url),
                    image_urls      = CASE WHEN array_length(EXCLUDED.image_urls, 1) > 0
                                          THEN EXCLUDED.image_urls
                                          ELSE content_items.image_urls END,
                    importance_score = GREATEST(EXCLUDED.importance_score, content_items.importance_score),
                    tags            = CASE WHEN array_length(EXCLUDED.tags, 1) > 0
                                          THEN EXCLUDED.tags
                                          ELSE content_items.tags END,
                    category        = COALESCE(EXCLUDED.category, content_items.category),
                    raw_metadata    = content_items.raw_metadata || EXCLUDED.raw_metadata,
                    embedding       = COALESCE(EXCLUDED.embedding, content_items.embedding)
                RETURNING id
                """,
                item.content_type,
                item.title,
                item.source_platform,
                item.source_url,
                date_val,
                published_val,
                item.summary,
                item.full_text,
                item.thumbnail_url,
                item.media_url,
                item.duration_sec,
                item.image_urls or [],
                item.importance_score,
                item.tags or [],
                item.category,
                json.dumps(item.raw_metadata or {}, ensure_ascii=False),
                _format_vector(item.embedding),
                content_hash,
            )
        return row["id"]

    async def upsert_batch(self, items: List[ContentItemInput]) -> List[int]:
        """批量插入/更新多条内容条目。返回 id 列表。"""
        ids = []
        for item in items:
            try:
                row_id = await self.upsert(item)
                ids.append(row_id)
            except Exception as exc:
                logger.warning("ContentRepository.upsert failed for %s: %s",
                               item.source_url, exc)
        return ids

    async def get_by_id(self, content_id: int) -> Optional[Dict]:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM content_items WHERE id = $1", content_id
            )
        if not row:
            return None
        result = dict(row)
        # asyncpg 返回 JSONB 列为字符串；解析为 Python 字典
        if isinstance(result.get("raw_metadata"), str):
            result["raw_metadata"] = json.loads(result["raw_metadata"])
        return result

    async def list_by_date(
        self,
        date_str,  # str (YYYY-MM-DD) 或 datetime.date
        content_type: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50,
        cursor_id: Optional[int] = None,
    ) -> List[Dict]:
        """基于游标的分页查询，按 (date_partition, id) 排序。"""
        pool = get_pool()
        # asyncpg 要求日期列使用 date 对象（而非字符串）
        if isinstance(date_str, str):
            date_str = date.fromisoformat(date_str)
        conditions = ["date_partition = $1"]
        params: list = [date_str]
        idx = 2

        if content_type:
            conditions.append(f"content_type = ${idx}")
            params.append(content_type)
            idx += 1

        if platform:
            conditions.append(f"source_platform = ${idx}")
            params.append(platform)
            idx += 1

        if cursor_id:
            conditions.append(f"id < ${idx}")
            params.append(cursor_id)
            idx += 1

        where = " AND ".join(conditions)
        params.append(limit)
        query = f"""
            SELECT id, content_type, title, source_platform, source_url,
                   published_at, summary, thumbnail_url, media_url,
                   duration_sec, importance_score, tags, category, date_partition
            FROM content_items
            WHERE {where}
            ORDER BY importance_score DESC, id DESC
            LIMIT ${idx}
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]

    async def search_fulltext(
        self,
        query: str,
        content_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """基于 pg_trgm 的标题和全文三元组相似度搜索。"""
        pool = get_pool()
        params: list = [query, query, limit]
        type_filter = ""
        if content_type:
            type_filter = "AND content_type = $4"
            params.append(content_type)

        sql = f"""
            SELECT id, content_type, title, source_platform, source_url,
                   published_at, summary, thumbnail_url, importance_score,
                   similarity(title, $1) AS title_sim
            FROM content_items
            WHERE title % $1 OR (full_text IS NOT NULL AND full_text % $2)
            {type_filter}
            ORDER BY title_sim DESC, importance_score DESC
            LIMIT $3
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def search_semantic(
        self,
        embedding: List[float],
        content_type: Optional[str] = None,
        date_from: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """基于向量余弦相似度的语义搜索。"""
        pool = get_pool()
        vec_str = _format_vector(embedding)
        conditions = ["embedding IS NOT NULL"]
        params: list = [vec_str, limit]
        idx = 3

        if content_type:
            conditions.append(f"content_type = ${idx}")
            params.append(content_type)
            idx += 1

        if date_from:
            conditions.append(f"date_partition >= ${idx}::date")
            params.append(date_from)
            idx += 1

        where = " AND ".join(conditions)
        sql = f"""
            SELECT id, content_type, title, source_platform, source_url,
                   published_at, summary, thumbnail_url, importance_score,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM content_items
            WHERE {where}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def get_trending(
        self,
        date_str,  # str (YYYY-MM-DD) 或 datetime.date
        content_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """获取指定日期的热点条目，按重要性评分排序。"""
        # list_by_date 内部自动处理 str→date 转换
        return await self.list_by_date(
            date_str, content_type=content_type, limit=limit
        )

    async def get_last_sync_time(self, date_str: str, source_type: str) -> Optional[str]:
        """Query the most recent sync timestamp for a given date and source type."""
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT synced_at FROM etl_sync_records
                   WHERE date_partition = $1 AND source_type = $2 AND status = 'success'
                   ORDER BY synced_at DESC LIMIT 1""",
                date_str, source_type,
            )
            return str(row["synced_at"]) if row else None

    async def record_sync(self, date_str: str, source_type: str, item_count: int) -> None:
        """Record a successful ETL sync."""
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO etl_sync_records (date_partition, source_type, item_count, status)
                   VALUES ($1, $2, $3, 'success')
                   ON CONFLICT (date_partition, source_type) DO UPDATE SET
                       synced_at = NOW(), item_count = etl_sync_records.item_count + EXCLUDED.item_count""",
                date_str, source_type, item_count,
            )

    async def list_by_category(
        self,
        date_str,
        category: str = "",
        limit: int = 20,
    ) -> List[Dict]:
        pool = get_pool()
        if isinstance(date_str, str):
            date_str = date.fromisoformat(date_str)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, content_type, title, source_platform, source_url,
                       published_at, summary, thumbnail_url, media_url,
                       duration_sec, importance_score, tags, category, date_partition
                FROM content_items
                WHERE date_partition = $1 AND category = $2
                ORDER BY importance_score DESC, id DESC
                LIMIT $3
                """,
                date_str, category, limit,
            )
        return [dict(r) for r in rows]

    async def mark_used(self, content_id: int, persona_id: str) -> None:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO content_usage_marks (content_id, persona_id)
                VALUES ($1, $2)
                ON CONFLICT (content_id, persona_id) DO NOTHING
                """,
                content_id, persona_id,
            )

    async def get_trending_topics(
        self,
        date_str,
        days: int = 1,
        limit: int = 10,
    ) -> List[Dict]:
        pool = get_pool()
        if isinstance(date_str, str):
            date_str = date.fromisoformat(date_str)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT category, COUNT(*) as count,
                       COUNT(DISTINCT source_platform) as sources,
                       AVG(importance_score) as avg_importance,
                       array_agg(DISTINCT unnested_tag) FILTER (WHERE unnested_tag IS NOT NULL) as top_tags
                FROM content_items
                LEFT JOIN LATERAL unnest(tags) AS unnested_tag ON true
                WHERE date_partition >= $1 - $2 * INTERVAL '1 day'
                  AND category IS NOT NULL AND category != ''
                GROUP BY category
                ORDER BY count DESC
                LIMIT $3
                """,
                date_str, days, limit,
            )
        return [dict(r) for r in rows]

    async def list_without_embedding(
        self, date_str: str, limit: int = 200
    ) -> List[Dict]:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, title, summary, ai_summary
                   FROM content_items
                   WHERE date_partition = $1::date AND embedding IS NULL
                   LIMIT $2""",
                date_str, limit,
            )
        return [dict(r) for r in rows]

    async def update_embedding(self, content_id: int, embedding: List[float]) -> None:
        pool = get_pool()
        vec_str = _format_vector(embedding)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE content_items SET embedding = $1::vector WHERE id = $2",
                vec_str, content_id,
            )

    async def get_stats(self) -> Dict:
        """获取整体统计数据。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM content_items")
            by_type = await conn.fetch(
                "SELECT content_type, COUNT(*) AS cnt FROM content_items "
                "GROUP BY content_type ORDER BY cnt DESC"
            )
            by_platform = await conn.fetch(
                "SELECT source_platform, COUNT(*) AS cnt FROM content_items "
                "GROUP BY source_platform ORDER BY cnt DESC LIMIT 20"
            )
            latest_date = await conn.fetchval(
                "SELECT MAX(date_partition) FROM content_items"
            )
        return {
            "total_items": total,
            "by_type": {r["content_type"]: r["cnt"] for r in by_type},
            "by_platform": {r["source_platform"]: r["cnt"] for r in by_platform},
            "latest_date": str(latest_date) if latest_date else None,
        }


# ================================================================
# KnowledgeRepository
# ================================================================

class KnowledgeRepository:
    """knowledge_entries 表的 CRUD 操作。"""

    async def upsert(self, entry: KnowledgeEntryInput) -> int:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_entries (
                    canonical_title, summary, full_text, category, tags,
                    image_urls, importance_score, embedding,
                    first_seen_at, last_seen_at, source_count
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8::vector,
                    $9::timestamptz, $10::timestamptz, $11
                )
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                entry.canonical_title,
                entry.summary,
                entry.full_text,
                entry.category,
                entry.tags or [],
                entry.image_urls or [],
                entry.importance_score,
                _format_vector(entry.embedding),
                entry.first_seen_at,
                entry.last_seen_at,
                entry.source_count,
            )
        return row["id"] if row else -1

    async def get_by_id(self, entry_id: int) -> Optional[Dict]:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM knowledge_entries WHERE id = $1", entry_id
            )
            if not row:
                return None
            result = dict(row)
            # 查询关联的 content_items
            content_rows = await conn.fetch(
                """
                SELECT ci.id, ci.title, ci.source_platform, ci.source_url,
                       ci.published_at
                FROM content_items ci
                JOIN knowledge_content_map kcm ON kcm.content_id = ci.id
                WHERE kcm.knowledge_id = $1
                ORDER BY ci.published_at DESC
                """,
                entry_id,
            )
            result["sources"] = [dict(r) for r in content_rows]
        return result

    async def list_recent(
        self,
        days: int = 7,
        category: Optional[str] = None,
        limit: int = 50,
        cursor_id: Optional[int] = None,
    ) -> List[Dict]:
        pool = get_pool()
        conditions = [
            f"first_seen_at >= NOW() - INTERVAL '{days} days'"
        ]
        params: list = []
        idx = 1

        if category:
            conditions.append(f"category = ${idx}")
            params.append(category)
            idx += 1

        if cursor_id:
            conditions.append(f"id < ${idx}")
            params.append(cursor_id)
            idx += 1

        params.append(limit)
        where = " AND ".join(conditions)
        sql = f"""
            SELECT id, canonical_title, summary, category, tags,
                   importance_score, source_count, first_seen_at, last_seen_at
            FROM knowledge_entries
            WHERE {where}
            ORDER BY importance_score DESC, id DESC
            LIMIT ${idx}
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def search_semantic(
        self,
        embedding: List[float],
        limit: int = 10,
        category: Optional[str] = None,
    ) -> List[Dict]:
        pool = get_pool()
        vec_str = _format_vector(embedding)
        conditions = ["embedding IS NOT NULL"]
        params: list = [vec_str, limit]
        idx = 3

        if category:
            conditions.append(f"category = ${idx}")
            params.append(category)
            idx += 1

        where = " AND ".join(conditions)
        sql = f"""
            SELECT id, canonical_title, summary, category, tags,
                   importance_score, source_count, first_seen_at,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM knowledge_entries
            WHERE {where}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def link_content(self, knowledge_id: int, content_id: int) -> None:
        """将 content_item 关联到 knowledge_entry。"""
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_content_map (knowledge_id, content_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                knowledge_id,
                content_id,
            )


# ================================================================
# 辅助函数
# ================================================================

def _make_hash(platform: str, url: str) -> str:
    return hashlib.md5(f"{platform}:{url}".encode()).hexdigest()


def _format_vector(vec: Optional[List[float]]) -> Optional[str]:
    """将 Python 列表格式化为 pgvector 字符串 '[1.0,2.0,...]'。"""
    if vec is None:
        return None
    return "[" + ",".join(str(float(v)) for v in vec) + "]"
