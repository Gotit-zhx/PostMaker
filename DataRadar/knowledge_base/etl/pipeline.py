"""
后处理管道：embedding 生成 + 知识聚合 + 缓存刷新。

数据已直写到 PostgreSQL content_items，此管道只做后处理。

阶段：
  1. embed       — 为缺少 embedding 的 content_items 生成向量
  2. aggregate   — 跨平台标题相似度分组 → knowledge_entries
  3. invalidate  — 刷新 Redis 缓存
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any, Dict, List, Optional

from knowledge_base.etl.embedder import BatchEmbedder
from knowledge_base.repository import (
    ContentItemInput,
    ContentRepository,
    KnowledgeRepository,
)

logger = logging.getLogger(__name__)


class ETLPipeline:
    """后处理管道：embedding + 聚合。"""

    def __init__(self, embedder: Optional[BatchEmbedder] = None):
        self.embedder = embedder
        self._content_repo = ContentRepository()
        self._knowledge_repo = KnowledgeRepository()

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "ETLPipeline":
        kb_cfg = config.get("KNOWLEDGE_BASE", {})
        embed_cfg = kb_cfg.get("EMBEDDING", {})

        embedder = None
        if embed_cfg.get("ENABLED"):
            ai_cfg = config.get("AI", {})
            embedder = BatchEmbedder(
                model=embed_cfg.get("MODEL", "text-embedding-3-small"),
                api_key=ai_cfg.get("API_KEY", ""),
                api_base=ai_cfg.get("API_BASE"),
                batch_size=int(embed_cfg.get("BATCH_SIZE", 50)),
                dimensions=int(embed_cfg.get("DIMENSIONS", 1536)),
            )

        return cls(embedder=embedder)

    async def run(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        if not date_str:
            date_str = date.today().isoformat()

        t0 = time.monotonic()
        stats = {"date": date_str, "embedded": 0, "aggregated": 0}

        logger.info("Post-processing starting for %s", date_str)

        if self.embedder:
            stats["embedded"] = await self._embed_missing(date_str)

        try:
            stats["aggregated"] = await self._aggregate(date_str)
        except Exception as exc:
            logger.warning("Aggregate failed (non-critical): %s", exc)

        try:
            await self._invalidate_cache(date_str)
        except Exception as exc:
            logger.warning("Cache invalidation failed: %s", exc)

        elapsed = time.monotonic() - t0
        logger.info(
            "Post-processing done for %s: %d embedded, %d aggregated in %.1fs",
            date_str, stats["embedded"], stats["aggregated"], elapsed,
        )
        return stats

    async def _embed_missing(self, date_str: str) -> int:
        """为缺少 embedding 的 content_items 生成向量。"""
        rows = await self._content_repo.list_without_embedding(date_str, limit=200)
        if not rows:
            return 0

        texts = [(r.get("ai_summary") or r.get("summary") or r["title"])[:2000] for r in rows]
        ids = [r["id"] for r in rows]

        logger.info("Embedding %d items", len(texts))
        vectors = await self.embedder.embed_batch(texts)

        count = 0
        for item_id, vec in zip(ids, vectors):
            if vec:
                await self._content_repo.update_embedding(item_id, vec)
                count += 1

        return count

    async def _aggregate(self, date_str: str) -> int:
        content_rows = await self._content_repo.list_by_date(date_str, limit=500)
        if not content_rows:
            return 0

        seen_titles: List[str] = []
        grouped: Dict[int, List[Dict]] = {}

        for row in content_rows:
            title = row["title"]
            placed = False
            for gi, ref_title in enumerate(seen_titles):
                if _title_similar(title, ref_title):
                    grouped[gi].append(row)
                    placed = True
                    break
            if not placed:
                gi = len(seen_titles)
                seen_titles.append(title)
                grouped[gi] = [row]

        count = 0
        multi_source = {gi: rows for gi, rows in grouped.items() if len(rows) >= 2}
        for gi, rows in multi_source.items():
            best = max(rows, key=lambda r: r.get("importance_score", 0))
            from knowledge_base.repository import KnowledgeEntryInput
            entry = KnowledgeEntryInput(
                canonical_title=best["title"],
                summary=best.get("summary"),
                category=best.get("category"),
                tags=best.get("tags") or [],
                importance_score=best.get("importance_score", 0),
                first_seen_at=str(best.get("published_at") or date_str),
                last_seen_at=str(best.get("published_at") or date_str),
                source_count=len(rows),
            )
            try:
                ke_id = await self._knowledge_repo.upsert(entry)
                if ke_id > 0:
                    for row in rows:
                        await self._knowledge_repo.link_content(ke_id, row["id"])
                    count += 1
            except Exception as exc:
                logger.debug("Aggregate upsert failed: %s", exc)

        return count

    async def _invalidate_cache(self, date_str: str) -> None:
        from knowledge_base.cache import get_cache
        cache = get_cache()
        await cache.delete_pattern(f"trending:{date_str}:*")
        await cache.delete(cache.stats_key())


def _title_similar(a: str, b: str, threshold: float = 0.6) -> bool:
    if not a or not b:
        return False
    a_lower = a.lower()
    b_lower = b.lower()
    if any('\u4e00' <= c <= '\u9fff' for c in a_lower + b_lower):
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a_lower, b_lower).ratio() >= threshold
    wa = set(a_lower.split())
    wb = set(b_lower.split())
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= threshold
