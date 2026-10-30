"""工作台 API 的本地集成测试。"""

from datetime import datetime, timezone

import httpx
import pytest

from postmaker.core.models import Draft, Material, Persona
from postmaker.workbench import app as workbench_app
from postmaker.workbench.store import WorkbenchStore


class FakeDataRadarClient:
    material = Material(
        id=11,
        title="AI 工具发布新版本",
        source_platform="example",
        source_url="https://example.com/articles/11",
        published_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
        summary="一条用于测试的素材摘要。",
        full_text="这是素材正文。",
        importance_score=4.5,
        tags=["AI"],
        category="AI",
        ai_summary="AI 工具更新摘要。",
    )

    def __init__(self, *args, **kwargs):
        self.api_base = args[0] if args else "http://fake"
        self.marked = []
        type(self).last_marked = self.marked

    async def get_trending(self, limit=30):
        return [self.material]

    async def list_content(self, limit=30):
        return [self.material]

    async def get_content_detail(self, material_id):
        assert material_id == self.material.id
        return self.material

    async def close(self):
        return None

    async def mark_used(self, content_id, persona_id):
        self.marked.append((content_id, persona_id))


class FakeGenerator:
    def __init__(self, *args, **kwargs):
        pass

    async def generate_batch(self, tasks):
        task = tasks[0]
        return [Draft(
            material_id=task.material.id,
            persona_id=task.persona.id,
            title="生成的标题",
            body="生成的正文。",
            model_used="fake-model",
        )]


class BrokenDataRadarClient(FakeDataRadarClient):
    async def get_trending(self, limit=30):
        raise RuntimeError("connection refused")


@pytest.fixture
def persona():
    return Persona(id="tech", name="科技评论家", description="测试 persona")


@pytest.mark.asyncio
async def test_workbench_api_flow(tmp_path, monkeypatch, persona):
    monkeypatch.setattr(workbench_app, "store", WorkbenchStore(str(tmp_path / "workbench.sqlite3")))
    monkeypatch.setattr(workbench_app, "DataRadarClient", FakeDataRadarClient)
    monkeypatch.setattr(workbench_app, "ContentGenerator", FakeGenerator)
    monkeypatch.setattr(
        workbench_app,
        "_personas",
        lambda: ({
            "dataradar": {"api_base": "http://fake", "timeout": 1},
            "ai": {"api_key": "test-key", "model": "fake-model"},
        }, [persona]),
    )

    transport = httpx.ASGITransport(app=workbench_app.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        materials = await client.get("/api/materials")
        assert materials.status_code == 200
        assert materials.json()["items"][0]["source_url"] == "https://example.com/articles/11"

        detail = await client.get("/api/materials/11")
        assert detail.status_code == 200
        assert detail.json()["importance_score"] == 4.5

        generated = await client.post(
            "/api/drafts/generate",
            json={"material_id": 11, "persona_id": "tech"},
        )
        assert generated.status_code == 200
        draft = generated.json()
        assert draft["status"] == "pending_review"
        assert FakeDataRadarClient.last_marked == [(11, "tech")]
        draft_id = draft["id"]

        blocked_export = await client.get(f"/api/drafts/{draft_id}/export.md")
        assert blocked_export.status_code == 409

        edited = await client.put(
            f"/api/drafts/{draft_id}",
            json={"title": "人工修改标题", "body": "人工修改正文。"},
        )
        assert edited.status_code == 200
        approved = await client.put(
            f"/api/drafts/{draft_id}",
            json={
                "title": "人工修改标题",
                "body": "人工修改正文。",
                "status": "approved",
            },
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        revisions = await client.get(f"/api/drafts/{draft_id}/revisions")
        assert revisions.status_code == 200
        assert len(revisions.json()["items"]) == 3

        exported = await client.get(f"/api/drafts/{draft_id}/export.md")
        assert exported.status_code == 200
        assert "status: approved" in exported.text
        assert "source: \"https://example.com/articles/11\"" in exported.text
        assert "人工修改正文。" in exported.text

        restored = await client.post(
            f"/api/drafts/{draft_id}/restore",
            json={"revision_id": revisions.json()["items"][-1]["id"]},
        )
        assert restored.status_code == 200
        assert restored.json()["title"] == "生成的标题"
        assert restored.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_generate_requires_ai_configuration(tmp_path, monkeypatch, persona):
    monkeypatch.setattr(workbench_app, "store", WorkbenchStore(str(tmp_path / "workbench.sqlite3")))
    monkeypatch.setattr(
        workbench_app,
        "_personas",
        lambda: ({"ai": {"api_key": "", "model": ""}}, [persona]),
    )

    transport = httpx.ASGITransport(app=workbench_app.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/drafts/generate",
            json={"material_id": 11, "persona_id": "tech"},
        )
    assert response.status_code == 503
    assert "AI_API_KEY" in response.json()["detail"]


@pytest.mark.asyncio
async def test_materials_reports_dataradar_failure(tmp_path, monkeypatch, persona):
    monkeypatch.setattr(workbench_app, "store", WorkbenchStore(str(tmp_path / "workbench.sqlite3")))
    monkeypatch.setattr(workbench_app, "DataRadarClient", BrokenDataRadarClient)
    monkeypatch.setattr(
        workbench_app,
        "_personas",
        lambda: ({"dataradar": {"api_base": "http://fake"}}, [persona]),
    )

    transport = httpx.ASGITransport(app=workbench_app.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/materials")
    assert response.status_code == 502
    assert "DataRadar" in response.json()["detail"]


@pytest.mark.asyncio
async def test_source_and_collection_proxy_endpoints(monkeypatch):
    calls = []

    async def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/api/v1/sources":
            return {"items": [], "count": 0}
        if path == "/api/v1/collect/status":
            return {"status": "completed", "job_id": "job-1"}
        return {"ok": True}

    monkeypatch.setattr(workbench_app, "_dataradar_request", fake_request)
    transport = httpx.ASGITransport(app=workbench_app.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/sources")).json()["count"] == 0
        assert (await client.post("/api/sources/rss", json={"url": "https://example.com/feed.xml"})).status_code == 201
        assert (await client.post("/api/sources/rss/test", json={"url": "https://example.com/feed.xml"})).status_code == 200
        assert (await client.post("/api/sources/demo/test")).status_code == 200
        assert (await client.post("/api/sources/demo/enable")).status_code == 200
        assert (await client.post("/api/sources/demo/disable")).status_code == 200
        assert (await client.delete("/api/sources/demo")).status_code == 200
        assert (await client.post("/api/collect")).status_code == 202
        assert (await client.get("/api/collect/status")).json()["status"] == "completed"

    paths = [path for _, path, _ in calls]
    assert paths == [
        "/api/v1/sources",
        "/api/v1/sources/rss",
        "/api/v1/sources/rss/test",
        "/api/v1/sources/demo/test",
        "/api/v1/sources/demo/enable",
        "/api/v1/sources/demo/disable",
        "/api/v1/sources/demo",
        "/api/v1/collect",
        "/api/v1/collect/status",
    ]
