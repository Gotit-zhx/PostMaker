import asyncio

from dataradar.collector import DataCollector
from dataradar.storage.base import RSSData, RSSItem
from dataradar.storage.manager import StorageManager
from knowledge_base.local_repository import LocalContentRepository


def test_collector_persists_fixture_and_closes_storage(tmp_path):
    async def scenario():
        db = tmp_path / "collector.sqlite3"
        collector = DataCollector({
            "TIMEZONE": "Asia/Shanghai",
            "RSS": {"ENABLED": True, "FEEDS": []},
            "KNOWLEDGE_BASE": {
                "ENABLED": False,
                "ENRICHER": {"ENABLED": False, "USE_PLAYWRIGHT": False},
                "SUMMARIZER": {"ENABLED": False},
                "EMBEDDING": {"ENABLED": False},
            },
            "WEB_SCRAPER": {"ENABLED": False},
        })
        collector.storage_manager = StorageManager(db_path=str(db))

        async def fetch_fixture():
            return RSSData(
                date="2026-10-30", crawl_time="15:00",
                items={"smoke": [RSSItem(
                    title="Collector pipeline smoke", feed_id="smoke",
                    url="https://example.test/collector-smoke", category="Engineering",
                )]},
                id_to_name={"smoke": "Smoke Feed"},
            )

        async def no_web_items():
            return []

        collector._fetch_rss = fetch_fixture
        collector._fetch_web_pages = no_web_items
        await collector.run()

        rows = await LocalContentRepository(str(db)).list_by_date("2026-10-30")
        assert len(rows) == 1
        assert rows[0]["title"] == "Collector pipeline smoke"
        assert collector.storage_manager._conn is None

    asyncio.run(scenario())
