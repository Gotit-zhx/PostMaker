"""SQLite repository used when PostgreSQL is not configured."""
from __future__ import annotations
import json, os, sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional


def _path() -> str:
    return os.getenv(
        "DATARADAR_SQLITE_PATH",
        str(Path(__file__).resolve().parents[1] / "output" / "dataradar.sqlite3"),
    )


def _decode(row):
    d = dict(row)
    for k, default in (("tags", []), ("image_urls", []), ("raw_metadata", {})):
        if isinstance(d.get(k), str):
            try: d[k] = json.loads(d[k])
            except json.JSONDecodeError: d[k] = default
    if isinstance(d.get("date_partition"), str):
        try: d["date_partition"] = date.fromisoformat(d["date_partition"])
        except ValueError: pass
    if isinstance(d.get("published_at"), str):
        try: d["published_at"] = datetime.fromisoformat(d["published_at"].replace("Z", "+00:00"))
        except ValueError: pass
    return d


class LocalContentRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _path()

    def _connect(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS content_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT, content_type TEXT NOT NULL DEFAULT 'text', title TEXT NOT NULL,
          source_platform TEXT NOT NULL, source_url TEXT NOT NULL, canonical_url TEXT, published_at TEXT,
          crawled_at TEXT, date_partition TEXT NOT NULL, summary TEXT, full_text TEXT, author TEXT, ai_summary TEXT,
          thumbnail_url TEXT, media_url TEXT, duration_sec INTEGER, image_urls TEXT NOT NULL DEFAULT '[]',
          feed_id TEXT, feed_name TEXT, crawl_count INTEGER NOT NULL DEFAULT 1, first_crawl_at TEXT,
          last_crawl_at TEXT, importance_score REAL NOT NULL DEFAULT 0, tags TEXT NOT NULL DEFAULT '[]', category TEXT,
          raw_metadata TEXT NOT NULL DEFAULT '{}', content_hash TEXT, UNIQUE(source_platform, source_url))""")
        conn.execute("CREATE TABLE IF NOT EXISTS content_usage_marks (content_id INTEGER, persona_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(content_id,persona_id))")
        conn.commit()
        return conn

    def _rows(self, sql, params=()):
        with self._connect() as conn:
            return [_decode(r) for r in conn.execute(sql, params).fetchall()]

    async def get_by_id(self, content_id: int):
        rows = self._rows("SELECT * FROM content_items WHERE id=?", (content_id,))
        return rows[0] if rows else None

    async def list_by_date(self, date_str, content_type=None, platform=None, limit=50, cursor_id=None):
        where, params = ["date_partition=?"], [str(date_str)]
        if content_type: where.append("content_type=?"); params.append(content_type)
        if platform: where.append("source_platform=?"); params.append(platform)
        if cursor_id: where.append("id<?"); params.append(cursor_id)
        params.append(limit)
        return self._rows(f"SELECT * FROM content_items WHERE {' AND '.join(where)} ORDER BY importance_score DESC,id DESC LIMIT ?", params)

    async def search_fulltext(self, query, content_type=None, limit=20):
        where = ["(title LIKE ? OR summary LIKE ? OR full_text LIKE ?)" ]
        params = [f"%{query}%"] * 3
        if content_type: where.append("content_type=?"); params.append(content_type)
        params.append(limit)
        return self._rows(f"SELECT * FROM content_items WHERE {' AND '.join(where)} ORDER BY importance_score DESC,id DESC LIMIT ?", params)

    async def get_trending(self, date_str, content_type=None, limit=50):
        return await self.list_by_date(date_str, content_type=content_type, limit=limit)

    async def list_by_category(self, date_str, category="", limit=20):
        return await self.list_by_date_category(date_str, category, limit)

    async def list_by_date_category(self, date_str, category, limit):
        return self._rows("SELECT id,content_type,title,source_platform,source_url,published_at,summary,thumbnail_url,media_url,duration_sec,importance_score,tags,category,date_partition FROM content_items WHERE date_partition=? AND category=? ORDER BY importance_score DESC,id DESC LIMIT ?", (str(date_str), category, limit))

    async def mark_used(self, content_id, persona_id):
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO content_usage_marks(content_id,persona_id) VALUES (?,?)", (content_id, persona_id)); conn.commit()

    async def get_trending_topics(self, date_str, days=1, limit=10):
        start = (date.fromisoformat(str(date_str)) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute("SELECT category,COUNT(*) count,COUNT(DISTINCT source_platform) sources,AVG(importance_score) avg_importance,tags FROM content_items WHERE date_partition>=? AND date_partition<=? AND category IS NOT NULL AND category!='' GROUP BY category ORDER BY count DESC LIMIT ?", (start, str(date_str), limit)).fetchall()
        out=[]
        for row in rows:
            tags=[]
            try: tags=json.loads(row["tags"] or "[]")
            except json.JSONDecodeError: pass
            out.append({"category":row["category"],"count":row["count"],"sources":row["sources"],"avg_importance":row["avg_importance"],"top_tags":tags[:10]})
        return out

    async def get_latest_date(self):
        with self._connect() as conn:
            return conn.execute("SELECT MAX(date_partition) FROM content_items").fetchone()[0]

    async def get_stats(self):
        with self._connect() as conn:
            total=conn.execute("SELECT COUNT(*) FROM content_items").fetchone()[0]
            by_type={r["content_type"]:r["cnt"] for r in conn.execute("SELECT content_type,COUNT(*) cnt FROM content_items GROUP BY content_type")}
            by_platform={r["source_platform"]:r["cnt"] for r in conn.execute("SELECT source_platform,COUNT(*) cnt FROM content_items GROUP BY source_platform ORDER BY cnt DESC LIMIT 20")}
            latest=conn.execute("SELECT MAX(date_partition) FROM content_items").fetchone()[0]
        return {"total_items":total,"by_type":by_type,"by_platform":by_platform,"latest_date":latest}

    async def get_feed_status(self):
        with self._connect() as conn:
            dates = [r[0] for r in conn.execute(
                "SELECT DISTINCT date_partition FROM content_items ORDER BY date_partition DESC LIMIT 10"
            )]
            rows = conn.execute(
                "SELECT feed_id,feed_name,COUNT(*) item_count FROM content_items "
                "WHERE date_partition=? AND feed_id IS NOT NULL GROUP BY feed_id,feed_name",
                (dates[0] if dates else "",),
            ).fetchall()
        return {
            "available_dates": dates,
            "total_dates": len(dates),
            "today_feeds": {r["feed_id"]: {"name": r["feed_name"] or r["feed_id"], "item_count": r["item_count"]} for r in rows},
        }
