"""Regression tests for the SQLite-backed RSS query service."""

import asyncio

from dataradar.services.data_service import DataService
from dataradar.storage.base import RSSData, RSSItem
from dataradar.storage.manager import StorageManager


def test_data_service_queries_local_sqlite(tmp_path, monkeypatch):
    db = tmp_path / "rss.db"
    monkeypatch.setenv("DATARADAR_SQLITE_PATH", str(db))

    async def scenario():
        manager = StorageManager(db_path=str(db))
        await manager.save_rss_data(RSSData(
            date="2026-10-30", crawl_time="12:00",
            items={"demo": [RSSItem(
                title="Local service search", feed_id="demo",
                url="https://example.test/local-service", summary="searchable summary",
            )]}, id_to_name={"demo": "Demo Feed"},
        ))
        await manager.close()

        service = DataService()
        latest = await service.get_latest_rss(limit=10)
        searched = await service.search_rss("searchable", limit=10, include_summary=True)
        status = await service.get_rss_feeds_status()
        assert latest[0]["feed_id"] == "demo"
        assert searched[0]["summary"] == "searchable summary"
        assert status["today_feeds"]["demo"]["item_count"] == 1

    asyncio.run(scenario())
