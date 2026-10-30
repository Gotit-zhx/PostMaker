# coding=utf-8
"""DataRadar storage manager with PostgreSQL and local SQLite backends."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dataradar.storage.base import RSSData, RSSItem
from dataradar.workspace import workspace_id, workspace_sqlite_path

logger = logging.getLogger(__name__)
_storage_managers: Dict[tuple[str, str], "StorageManager"] = {}


class StorageManager:
    """Persist collected RSS data to PostgreSQL when configured, otherwise SQLite."""

    def __init__(self, dsn: str = "", db_path: str | None = None):
        self.dsn = (dsn or "").strip()
        self.db_path = db_path or (
            str(workspace_sqlite_path()) if workspace_id() != "default" else os.getenv(
                "DATARADAR_SQLITE_PATH",
                str(Path(__file__).resolve().parents[2] / "output" / "dataradar.sqlite3"),
            )
        )
        self._pool = None
        self._conn: sqlite3.Connection | None = None

    @property
    def backend_name(self) -> str:
        return "postgresql" if self.dsn else "sqlite"

    async def init(self):
        if self.dsn:
            if self._pool is not None:
                return
            from knowledge_base.db import init_pool, get_pool
            await init_pool(self.dsn)
            self._pool = get_pool()
            logger.info("[存储] PostgreSQL 连接池就绪")
            return
        if self._conn is not None:
            return
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS content_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_type TEXT NOT NULL DEFAULT 'text', title TEXT NOT NULL,
                source_platform TEXT NOT NULL, source_url TEXT NOT NULL,
                canonical_url TEXT, published_at TEXT, crawled_at TEXT,
                date_partition TEXT NOT NULL, summary TEXT, full_text TEXT,
                author TEXT, ai_summary TEXT, thumbnail_url TEXT, media_url TEXT,
                duration_sec INTEGER, image_urls TEXT NOT NULL DEFAULT '[]',
                feed_id TEXT, feed_name TEXT, crawl_count INTEGER NOT NULL DEFAULT 1,
                first_crawl_at TEXT, last_crawl_at TEXT, importance_score REAL NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]', category TEXT, raw_metadata TEXT NOT NULL DEFAULT '{}',
                content_hash TEXT, UNIQUE(source_platform, source_url)
            );
            CREATE INDEX IF NOT EXISTS idx_content_date ON content_items(date_partition);
            CREATE INDEX IF NOT EXISTS idx_content_category ON content_items(category);
            CREATE TABLE IF NOT EXISTS content_usage_marks (
                content_id INTEGER NOT NULL, persona_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(content_id, persona_id)
            );
            """
        )
        self._conn.commit()
        logger.info("[存储] SQLite 数据库就绪: %s", path)

    async def close(self):
        if self._pool is not None:
            from knowledge_base.db import close_pool
            await close_pool()
            self._pool = None
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLite storage is not initialized")
        return self._conn

    async def save_rss_data(self, rss_data: RSSData) -> bool:
        if not self.dsn:
            await self.init()
            conn = self._ensure_conn()
            now = datetime.now(timezone.utc).isoformat()
            date_partition = rss_data.date or datetime.now().strftime("%Y-%m-%d")
            saved = 0
            for feed_id, items in rss_data.items.items():
                feed_name = rss_data.id_to_name.get(feed_id, feed_id)
                for item in items:
                    source_platform = f"rss-{feed_id}"
                    url = item.url or f"urn:dataradar:{hashlib.sha1(item.title.encode()).hexdigest()}"
                    tags = item.tags or []
                    values = (
                        item.title or "(untitled)", source_platform, url, url,
                        item.published_at or None, now, date_partition,
                        item.summary or None, item.full_text or None, item.author or None,
                        item.ai_summary or None, item.thumbnail_url or None, item.enclosure_url or None,
                        item.duration_sec or None, feed_id, feed_name, now, now,
                        float(item.importance_score or 0), json.dumps(tags, ensure_ascii=False),
                        item.category or None, json.dumps({"crawl_time": item.crawl_time}, ensure_ascii=False),
                        hashlib.md5(f"{source_platform}:{url}".encode()).hexdigest(),
                    )
                    conn.execute(
                        """INSERT INTO content_items
                        (content_type,title,source_platform,source_url,canonical_url,published_at,crawled_at,date_partition,
                         summary,full_text,author,ai_summary,thumbnail_url,media_url,duration_sec,feed_id,feed_name,
                         crawl_count,first_crawl_at,last_crawl_at,importance_score,tags,category,raw_metadata,content_hash)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?)
                        ON CONFLICT(source_platform,source_url) DO UPDATE SET
                          title=excluded.title, summary=COALESCE(excluded.summary,content_items.summary),
                          full_text=COALESCE(excluded.full_text,content_items.full_text),
                          ai_summary=COALESCE(excluded.ai_summary,content_items.ai_summary),
                          author=COALESCE(excluded.author,content_items.author),
                          crawl_count=content_items.crawl_count+1, last_crawl_at=excluded.last_crawl_at,
                          importance_score=MAX(excluded.importance_score,content_items.importance_score),
                          tags=CASE WHEN excluded.tags != '[]' THEN excluded.tags ELSE content_items.tags END,
                          category=COALESCE(excluded.category,content_items.category)""",
                        (item.content_type or "text", *values),
                    )
                    saved += 1
            conn.commit()
            return saved > 0

        if self._pool is None:
            await self.init()
        now = datetime.now(timezone.utc)
        date_partition = rss_data.date or now.strftime("%Y-%m-%d")
        upserted = 0
        for feed_id, items in rss_data.items.items():
            feed_name = rss_data.id_to_name.get(feed_id, feed_id)
            for item in items:
                try:
                    await self._upsert_item(item, feed_id, feed_name, date_partition, now)
                    upserted += 1
                except Exception as exc:
                    logger.warning("[存储] UPSERT 失败 (%s): %s", item.title[:30], exc)
        return upserted > 0

    async def _upsert_item(self, item, feed_id, feed_name, date_partition, now):
        source_platform = f"rss-{feed_id}"
        source_url = item.url or ""
        published_at = None
        if item.published_at:
            try:
                published_at = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO content_items
                (content_type,title,source_platform,source_url,canonical_url,published_at,crawled_at,date_partition,
                 summary,full_text,author,ai_summary,thumbnail_url,media_url,duration_sec,feed_id,feed_name,
                 crawl_count,first_crawl_at,last_crawl_at,importance_score,tags,category,content_hash)
                VALUES ($1,$2,$3,$4,$4,$5,$6,$7::date,$8,$9,$10,$11,$12,$13,$14,$15,$16,1,$6,$6,$17,$18,$19,$20)
                ON CONFLICT(source_platform,source_url) DO UPDATE SET crawl_count=content_items.crawl_count+1,
                last_crawl_at=EXCLUDED.crawled_at, full_text=COALESCE(NULLIF(EXCLUDED.full_text,''),content_items.full_text),
                ai_summary=COALESCE(NULLIF(EXCLUDED.ai_summary,''),content_items.ai_summary),
                importance_score=GREATEST(EXCLUDED.importance_score,content_items.importance_score),
                tags=COALESCE(EXCLUDED.tags,content_items.tags),category=COALESCE(EXCLUDED.category,content_items.category)""",
                item.content_type or "text", item.title, source_platform, source_url, published_at, now, date_partition,
                item.summary or None, item.full_text or None, item.author or None, item.ai_summary or None,
                item.thumbnail_url or None, item.enclosure_url or None, item.duration_sec or None, feed_id, feed_name,
                float(item.importance_score or 0), item.tags or [], item.category or None,
                hashlib.md5(f"{source_platform}:{source_url}".encode()).hexdigest())

    async def detect_new_rss_items(self, rss_data: RSSData) -> List[RSSItem]:
        if not self.dsn:
            await self.init(); conn = self._ensure_conn(); result=[]
            for feed_id, items in rss_data.items.items():
                for item in items:
                    if not item.url: continue
                    found = conn.execute("SELECT 1 FROM content_items WHERE source_platform=? AND source_url=?", (f"rss-{feed_id}", item.url)).fetchone()
                    if not found: result.append(item)
            return result
        if self._pool is None: await self.init()
        result=[]
        for feed_id, items in rss_data.items.items():
            urls=[i.url for i in items if i.url]
            if not urls: continue
            async with self._pool.acquire() as conn:
                rows=await conn.fetch("SELECT source_url FROM content_items WHERE source_platform=$1 AND source_url=ANY($2)", f"rss-{feed_id}", urls)
            existing={r["source_url"] for r in rows}
            result.extend(i for i in items if i.url and i.url not in existing)
        return result

    @staticmethod
    def _decode(row):
        d=dict(row)
        for key, default in (("tags", []),("image_urls", []),("raw_metadata", {})):
            val=d.get(key)
            if isinstance(val, str):
                try: d[key]=json.loads(val)
                except json.JSONDecodeError: d[key]=default
        for key in ("published_at","date_partition"):
            if d.get(key) and key == "date_partition":
                try: d[key]=datetime.strptime(d[key], "%Y-%m-%d").date()
                except ValueError: pass
        return d

    async def get_content_by_date(self, date: str, feed_ids=None, limit=200):
        if not self.dsn:
            await self.init(); conn=self._ensure_conn(); params=[date]; where="date_partition=?"
            if feed_ids: where += " AND feed_id IN (%s)" % ",".join("?"*len(feed_ids)); params.extend(feed_ids)
            rows=conn.execute(f"SELECT * FROM content_items WHERE {where} ORDER BY importance_score DESC,published_at DESC LIMIT ?", (*params,limit)).fetchall()
            return [self._decode(r) for r in rows]
        if self._pool is None: await self.init()
        async with self._pool.acquire() as conn:
            if feed_ids: rows=await conn.fetch("SELECT * FROM content_items WHERE date_partition=$1::date AND source_platform=ANY($2) ORDER BY importance_score DESC,published_at DESC LIMIT $3", date,[f"rss-{x}" for x in feed_ids],limit)
            else: rows=await conn.fetch("SELECT * FROM content_items WHERE date_partition=$1::date ORDER BY importance_score DESC,published_at DESC LIMIT $2",date,limit)
        return [dict(r) for r in rows]

    async def search_content(self, keyword, days=7, limit=50):
        if not self.dsn:
            await self.init(); conn=self._ensure_conn(); rows=conn.execute("SELECT * FROM content_items WHERE date_partition >= date('now', ?) AND (title LIKE ? OR summary LIKE ? OR full_text LIKE ?) ORDER BY published_at DESC LIMIT ?", (f"-{int(days)} day",f"%{keyword}%",f"%{keyword}%",f"%{keyword}%",limit)).fetchall(); return [self._decode(r) for r in rows]
        if self._pool is None: await self.init()
        async with self._pool.acquire() as conn: rows=await conn.fetch("SELECT * FROM content_items WHERE date_partition >= CURRENT_DATE - $1 * INTERVAL '1 day' AND (title ILIKE '%'||$2||'%' OR summary ILIKE '%'||$2||'%') ORDER BY published_at DESC LIMIT $3",days,keyword,limit)
        return [dict(r) for r in rows]

    async def get_feeds_status(self):
        if not self.dsn:
            await self.init(); conn=self._ensure_conn(); rows=conn.execute("SELECT feed_id,feed_name,COUNT(*) item_count,MIN(date_partition) first_date,MAX(date_partition) last_date FROM content_items WHERE feed_id IS NOT NULL GROUP BY feed_id,feed_name ORDER BY item_count DESC").fetchall(); return {"feeds":[dict(r) for r in rows],"generated_at":datetime.now().isoformat()}
        if self._pool is None: await self.init()
        async with self._pool.acquire() as conn: rows=await conn.fetch("SELECT feed_id,feed_name,COUNT(*) item_count,MIN(date_partition) first_date,MAX(date_partition) last_date FROM content_items WHERE feed_id IS NOT NULL GROUP BY feed_id,feed_name ORDER BY item_count DESC")
        return {"feeds":[dict(r) for r in rows],"generated_at":datetime.now().isoformat()}

    def cleanup(self):
        pass


def get_storage_manager(dsn: str = "", force_new: bool = False) -> StorageManager:
    key = (workspace_id(), dsn or "")
    if force_new or key not in _storage_managers:
        manager = StorageManager(dsn=dsn)
        _storage_managers[key] = manager
    manager = _storage_managers[key]
    return manager
