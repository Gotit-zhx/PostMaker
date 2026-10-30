"""平台发布适配器测试。"""

import pytest

from postmaker.workbench.platforms import adapt_draft, list_platforms
from postmaker.workbench.source_presets import list_source_presets


@pytest.fixture
def approved_draft():
    return {
        "id": 1,
        "title": "AI 工具更新",
        "body": "## 重点\n\n这是正文。\n\n- 一个要点\n- 第二个要点",
        "status": "approved",
        "material": {
            "source_platform": "demo",
            "source_url": "https://example.com/article",
            "category": "科技",
            "tags": ["AI", "开源"],
        },
    }


def test_all_platforms_return_normalized_payload(approved_draft):
    ids = {item["id"] for item in list_platforms()}
    assert ids == {"wechat", "zhihu", "xiaohongshu", "x", "linkedin", "generic"}
    for platform in ids:
        result = adapt_draft(approved_draft, platform)
        assert result["platform"] == platform
        assert result["title"]
        assert result["body"]
        assert isinstance(result["warnings"], list)
        assert "https://example.com/article" in result["source"]


def test_x_splits_long_content_into_thread(approved_draft):
    approved_draft["body"] = "\n\n".join(["一段很长的内容。" * 40] * 4)
    result = adapt_draft(approved_draft, "x")
    assert len(result["thread"]) > 1
    assert "线程" in " ".join(result["warnings"])


def test_xiaohongshu_warns_when_no_media(approved_draft):
    result = adapt_draft(approved_draft, "xiaohongshu")
    assert any("配图" in item for item in result["warnings"])
    assert "#科技" in result["caption"]


def test_source_presets_use_configured_rsshub_base(monkeypatch):
    monkeypatch.setenv("RSSHUB_SOURCE_BASE_URL", "http://rsshub:1200")
    presets = list_source_presets()
    rsshub = next(item for item in presets if item["id"] == "rsshub-solidot")
    assert rsshub["url"] == "http://rsshub:1200/solidot"
    assert rsshub["provider"] == "RSSHub"
