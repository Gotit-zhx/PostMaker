"""Regression tests for the local collection-to-API workflow."""
import asyncio

from dataradar.storage.base import RSSData, RSSItem
from dataradar.storage.manager import StorageManager
from knowledge_base.local_repository import LocalContentRepository


def test_sqlite_collection_is_visible_to_api_repository(tmp_path, monkeypatch):
    db = tmp_path / "radar.db"
    monkeypatch.setenv("DATARADAR_SQLITE_PATH", str(db))

    async def scenario():
        manager = StorageManager()
        payload = RSSData(
            date="2026-10-30", crawl_time="12:00",
            items={"demo": [RSSItem(
                title="SQLite closes the loop", feed_id="demo",
                url="https://example.test/story", summary="Local API searchable",
                tags=["sqlite", "api"], category="Engineering", importance_score=4.2,
            )]},
            id_to_name={"demo": "Demo Feed"},
        )
        assert await manager.save_rss_data(payload)
        await manager.close()

        repo = LocalContentRepository()
        listed = await repo.list_by_date("2026-10-30")
        assert len(listed) == 1
        assert listed[0]["title"] == "SQLite closes the loop"
        assert listed[0]["tags"] == ["sqlite", "api"]
        assert len(await repo.search_fulltext("searchable")) == 1
        assert len(await repo.get_trending("2026-10-30")) == 1
        assert len(await repo.list_by_category("2026-10-30", "Engineering")) == 1
        await repo.mark_used(listed[0]["id"], "persona-a")
        assert await repo.get_by_id(listed[0]["id"])
        assert (await repo.get_stats())["total_items"] == 1

    asyncio.run(scenario())


def test_sqlite_deduplicates_rss_url_and_tracks_recrawls(tmp_path):
    async def scenario():
        manager = StorageManager(db_path=str(tmp_path / "dedupe.db"))
        payload = RSSData("2026-10-30", "12:00", {
            "demo": [RSSItem(title="Story", feed_id="demo", url="https://example.test/1")]
        }, {"demo": "Demo"})
        await manager.save_rss_data(payload)
        await manager.save_rss_data(payload)
        rows = await manager.get_content_by_date("2026-10-30")
        assert len(rows) == 1
        assert rows[0]["crawl_count"] == 2
        await manager.close()

    asyncio.run(scenario())
