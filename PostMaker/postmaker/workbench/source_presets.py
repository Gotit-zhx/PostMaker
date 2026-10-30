"""Curated beginner-friendly content source presets."""

from __future__ import annotations

import os
from typing import Any

# Keep this list intentionally small. A preset is a starting point, not a promise
# that an upstream website will remain available forever.
_PRESETS: tuple[dict[str, Any], ...] = (
    {"id": "rsshub-solidot", "name": "Solidot", "category": "科技", "route": "/solidot", "description": "开源、科学和科技新闻", "max_age_days": 3},
    {"id": "rsshub-sspai", "name": "少数派 Matrix", "category": "产品", "route": "/sspai/matrix", "description": "效率工具与数字生活", "max_age_days": 5},
    {"id": "rsshub-apnews-tech", "name": "AP News Technology", "category": "科技", "route": "/apnews/topics/technology", "description": "英文科技新闻", "max_age_days": 2},
    {"id": "rsshub-reuters-world", "name": "Reuters World", "category": "商业", "route": "/reuters/world", "description": "国际与商业资讯", "max_age_days": 2},
    {"id": "devto", "name": "Dev.to", "category": "开发", "url": "https://dev.to/feed", "description": "开发者社区文章", "max_age_days": 3},
    {"id": "openai-blog", "name": "OpenAI Blog", "category": "AI", "url": "https://openai.com/blog/rss.xml", "description": "AI 产品与研究动态", "max_age_days": 30},
)


def _base_url() -> str:
    return os.getenv("RSSHUB_SOURCE_BASE_URL", os.getenv("RSSHUB_BASE_URL", "http://localhost:1200")).rstrip("/")


def list_source_presets() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for preset in _PRESETS:
        item = dict(preset)
        if item.get("route"):
            item["url"] = f"{_base_url()}{item['route']}"
            item["provider"] = "RSSHub"
        else:
            item["provider"] = "RSS"
        item["status_hint"] = "建议先测试；上游站点变更后可能暂时不可用"
        result.append(item)
    return result


def get_source_preset(preset_id: str) -> dict[str, Any] | None:
    return next((item for item in list_source_presets() if item["id"] == preset_id), None)
