"""工作台平台适配与图文导出测试。"""

import io
import zipfile

import pytest
from fastapi import HTTPException

from postmaker.workbench import app as workbench_app
from postmaker.workbench.store import WorkbenchStore


@pytest.mark.asyncio
async def test_approved_draft_export_package_contains_media_manifest(tmp_path, monkeypatch):
    store = WorkbenchStore(str(tmp_path / "workbench.sqlite3"))
    monkeypatch.setattr(workbench_app, "store", store)
    draft = store.create_draft(
        {
            "id": 9,
            "title": "带图素材",
            "source_url": "https://example.com/article",
            "source_platform": "demo",
            "image_urls": ["https://example.com/image.jpg"],
            "tags": ["AI"],
        },
        "tech", "科技评论家", "带图文章", "## 正文\n\n内容", "test-model",
    )
    store.update_draft(draft["id"], draft["title"], draft["body"], "approved")
    response = await workbench_app.export_package(draft["id"], "wechat")
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        names = set(archive.namelist())
        assert {"draft.md", "publish.txt", "publish.json", "media-manifest.json"} <= names
        assert "https://example.com/image.jpg" in archive.read("media-manifest.json").decode()


@pytest.mark.asyncio
async def test_adaptation_export_rejects_pending_draft(tmp_path, monkeypatch):
    store = WorkbenchStore(str(tmp_path / "workbench.sqlite3"))
    monkeypatch.setattr(workbench_app, "store", store)
    draft = store.create_draft({"id": 2}, "tech", "科技评论家", "标题", "正文", "test-model")
    with pytest.raises(HTTPException) as exc:
        await workbench_app.export_package(draft["id"], "generic")
    assert exc.value.status_code == 409
