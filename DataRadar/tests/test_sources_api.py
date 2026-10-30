"""DataRadar 自助式数据源 API 测试。"""

import asyncio

import httpx
import pytest

from api_server.main import app
from api_server.routers import sources


class FakeManager:
    def __init__(self):
        self.feeds = [{"id": "demo", "name": "Demo", "url": "https://example.com/feed.xml", "enabled": True, "max_age_days": 3, "content_type": "text"}]
        self.targets = []

    def list_feeds(self):
        return list(self.feeds)

    def list_targets(self):
        return list(self.targets)

    def add_feed(self, **kwargs):
        if any(item["id"] == kwargs.get("id") for item in self.feeds):
            raise ValueError("RSS 源 ID 已存在")
        item = {"id": kwargs.get("id") or "new", "name": kwargs.get("name") or "New", "url": kwargs["url"], "enabled": kwargs.get("enabled", True), "max_age_days": kwargs.get("max_age_days", 3), "content_type": "text"}
        self.feeds.append(item)
        return {"id": item["id"], "name": item["name"], "url": item["url"], "status": "added"}

    def test_feed(self, value):
        return {"success": True, "feed_name": "Demo", "url": "https://example.com/feed.xml", "item_count": 1, "items": [{"title": "Item", "url": "https://example.com/item"}]}

    def test_target(self, value):
        return {"success": True, "item_count": 0, "items": []}

    def remove_source(self, source_id):
        before = len(self.feeds) + len(self.targets)
        self.feeds = [item for item in self.feeds if item["id"] != source_id]
        self.targets = [item for item in self.targets if item["id"] != source_id]
        return len(self.feeds) + len(self.targets) != before

    def enable_source(self, source_id):
        for item in self.feeds + self.targets:
            if item["id"] == source_id:
                item["enabled"] = True
                return True
        return False

    def disable_source(self, source_id):
        for item in self.feeds + self.targets:
            if item["id"] == source_id:
                item["enabled"] = False
                return True
        return False


@pytest.fixture
def client(monkeypatch):
    manager = FakeManager()
    monkeypatch.setattr(sources, "_manager", lambda: manager)
    # The route-level lifecycle test uses a fake manager and should not depend
    # on the host's DNS configuration; URL policy has dedicated unit tests.
    monkeypatch.setattr(sources, "validate_public_url", lambda value: value)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_source_lifecycle_and_validation(client):
    async with client as http:
        listed = await http.get("/api/v1/sources")
        assert listed.status_code == 200
        assert listed.json()["count"] == 1

        invalid = await http.post("/api/v1/sources/rss", json={"url": "ftp://invalid"})
        assert invalid.status_code == 422

        added = await http.post("/api/v1/sources/rss", json={"id": "new", "url": "https://example.com/new.xml"})
        assert added.status_code == 201
        assert added.json()["id"] == "new"

        tested = await http.post("/api/v1/sources/rss/test", json={"url": "https://example.com/new.xml"})
        assert tested.status_code == 200
        assert tested.json()["item_count"] == 1

        disabled = await http.post("/api/v1/sources/new/disable")
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False
        deleted = await http.delete("/api/v1/sources/new")
        assert deleted.status_code == 200
        assert (await http.delete("/api/v1/sources/missing")).status_code == 404


@pytest.mark.asyncio
async def test_collection_status_and_duplicate_trigger(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    class FakeCollector:
        def __init__(self, config):
            pass

        async def run(self):
            started.set()
            await release.wait()

    monkeypatch.setattr(sources, "load_config", lambda: {})
    monkeypatch.setattr(sources, "DataCollector", FakeCollector)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.post("/api/v1/collect")
        assert response.status_code == 202
        await started.wait()
        duplicate = await http.post("/api/v1/collect")
        assert duplicate.status_code == 409
        assert (await http.get("/api/v1/collect/status")).json()["status"] == "running"
        release.set()
        for _ in range(20):
            await asyncio.sleep(0)
            if (await http.get("/api/v1/collect/status")).json()["status"] != "running":
                break
        assert (await http.get("/api/v1/collect/status")).json()["status"] == "completed"

