"""SQLite workspace 路径和 DataRadar 缓存键隔离测试。"""

import asyncio

import httpx
import pytest

from api_server.main import app
from dataradar.storage import get_storage_manager
from dataradar.core.loader import load_config
from dataradar.source_manager import SourceManager
from dataradar.workspace import reset_workspace, set_workspace_id, workspace_signature
from knowledge_base.local_repository import LocalContentRepository


def test_local_repository_isolated_by_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("DATARADAR_WORKSPACES_DIR", str(tmp_path / "workspaces"))

    token_a = set_workspace_id("ws_workspace_a")
    try:
        repo_a = LocalContentRepository()
        repo_a._connect().close()
        path_a = repo_a.db_path
    finally:
        reset_workspace(token_a)

    token_b = set_workspace_id("ws_workspace_b")
    try:
        repo_b = LocalContentRepository()
        repo_b._connect().close()
        path_b = repo_b.db_path
    finally:
        reset_workspace(token_b)

    assert path_a != path_b
    assert "ws_workspace_a" in path_a
    assert "ws_workspace_b" in path_b


def test_storage_manager_cache_key_includes_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("DATARADAR_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    token_a = set_workspace_id("ws_workspace_a")
    try:
        manager_a = get_storage_manager(force_new=True)
    finally:
        reset_workspace(token_a)
    token_b = set_workspace_id("ws_workspace_b")
    try:
        manager_b = get_storage_manager()
    finally:
        reset_workspace(token_b)
    assert manager_a.db_path != manager_b.db_path
    asyncio.run(manager_a.close())
    asyncio.run(manager_b.close())


def test_workspace_bootstrap_does_not_copy_shared_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("DATARADAR_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    shared_config = tmp_path / "shared-config.yaml"
    shared_config.write_text(
        "rss:\n  feeds:\n    - id: shared\n      name: Shared\n      url: https://shared.example/feed.xml\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(shared_config))
    token = set_workspace_id("ws_new_user")
    try:
        manager = SourceManager()
        assert manager.list_feeds() == []
        assert manager.list_targets() == []
        config = load_config()
        assert config["RSS"]["FEEDS"] == []
        assert config["WEB_SCRAPER"]["TARGETS"] == []
    finally:
        reset_workspace(token)


@pytest.mark.asyncio
async def test_workspace_signature_is_required_for_api(monkeypatch):
    monkeypatch.setenv("DATARADAR_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSPACE_AUTH_SECRET", "test-secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/collect/status")).status_code == 401
        wrong = await client.get(
            "/api/v1/collect/status",
            headers={"X-Workspace-ID": "ws_workspace_a", "X-Workspace-Signature": "bad"},
        )
        assert wrong.status_code == 401
        valid = await client.get(
            "/api/v1/collect/status",
            headers={
                "X-Workspace-ID": "ws_workspace_a",
                "X-Workspace-Signature": workspace_signature("ws_workspace_a"),
            },
        )
        assert valid.status_code == 200
        assert valid.json()["status"] == "idle"
