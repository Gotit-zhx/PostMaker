"""验证 PostMaker 代理到 DataRadar 时的 workspace 签名和数据隔离。"""

from pathlib import Path
import sys

import httpx
import pytest

from api_server.main import app as dataradar_app
from api_server.routers import sources

# 该测试同时加载仓库内的 PostMaker 工作台，覆盖两个服务之间的真实请求边界。
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PostMaker"))
from postmaker.workbench import app as workbench_app  # noqa: E402
from postmaker.workbench.workspace import reset_workspace, set_workspace_id  # noqa: E402


@pytest.mark.asyncio
async def test_postmaker_proxy_preserves_workspace_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("DATARADAR_AUTH_REQUIRED", "1")
    monkeypatch.setenv("WORKSPACE_AUTH_SECRET", "cross-service-test-secret")
    monkeypatch.setenv("DATARADAR_WORKSPACES_DIR", str(tmp_path / "dataradar-workspaces"))
    monkeypatch.setattr(sources, "validate_public_url", lambda value: value)
    monkeypatch.setattr(
        workbench_app,
        "load_config",
        lambda: {"dataradar": {"api_base": "http://dataradar", "timeout": 5}},
    )

    class InProcessDataRadarClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.ASGITransport(app=dataradar_app)
            kwargs["base_url"] = "http://dataradar"
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(workbench_app.httpx, "AsyncClient", InProcessDataRadarClient)

    async def proxy_for(workspace: str, method: str, path: str, **kwargs):
        token = set_workspace_id(workspace)
        try:
            return await workbench_app._dataradar_request(method, path, **kwargs)
        finally:
            reset_workspace(token)

    await proxy_for(
        "ws_cross_service_a",
        "POST",
        "/api/v1/sources/rss",
        json={"id": "source-a", "name": "Source A", "url": "https://example.com/a.xml"},
    )
    a_sources = await proxy_for("ws_cross_service_a", "GET", "/api/v1/sources")
    b_sources = await proxy_for("ws_cross_service_b", "GET", "/api/v1/sources")

    assert [item["id"] for item in a_sources["items"]] == ["source-a"]
    assert b_sources["items"] == []

    await proxy_for(
        "ws_cross_service_b",
        "POST",
        "/api/v1/sources/rss",
        json={"id": "source-b", "name": "Source B", "url": "https://example.com/b.xml"},
    )
    a_sources_again = await proxy_for("ws_cross_service_a", "GET", "/api/v1/sources")
    b_sources_again = await proxy_for("ws_cross_service_b", "GET", "/api/v1/sources")

    assert [item["id"] for item in a_sources_again["items"]] == ["source-a"]
    assert [item["id"] for item in b_sources_again["items"]] == ["source-b"]
