"""工作台登录、CSRF 和 workspace 隔离测试。"""

import httpx
import pytest

from postmaker.workbench import app as workbench_app
from postmaker.workbench.auth import AuthStore
from postmaker.workbench.store import WorkbenchStore


@pytest.mark.asyncio
async def test_auth_register_login_csrf_and_workspace_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTMAKER_AUTH_REQUIRED", "1")
    monkeypatch.setattr(workbench_app, "auth_store", AuthStore(tmp_path / "auth.sqlite3"))
    monkeypatch.setattr(workbench_app, "store", WorkbenchStore(tmp_path / "default.sqlite3"))
    monkeypatch.setattr(workbench_app, "_personas", lambda: ({"ai": {}}, []))

    transport = httpx.ASGITransport(app=workbench_app.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/register", json={"email": "a@example.com", "password": "password-a"})
        assert response.status_code == 201
        csrf = response.cookies.get("pm_csrf")
        assert csrf

        assert (await client.get("/api/drafts")).status_code == 200
        blocked = await client.put("/api/drafts/1", json={"title": "x", "body": "y"})
        assert blocked.status_code == 403

        created = await client.post("/api/drafts/generate", json={"material_id": 1, "persona_id": "missing"}, headers={"X-CSRF-Token": csrf})
        assert created.status_code == 404

        duplicate = await client.post("/api/auth/register", json={"email": "a@example.com", "password": "password-a"})
        assert duplicate.status_code == 422

        await client.post("/api/auth/logout")
        assert (await client.get("/api/drafts")).status_code == 401

        login = await client.post("/api/auth/login", json={"email": "a@example.com", "password": "bad-password"})
        assert login.status_code == 401
