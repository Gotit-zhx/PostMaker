import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from postmaker.core.models import (
    Material,
    Persona,
    PersonaInterests,
    PersonaStyle,
)


MOCK_CONTENT_ITEM_AI = {
    "id": 42,
    "content_type": "text",
    "title": "OpenAI 发布 GPT-5",
    "source_platform": "rss-hacker-news",
    "source_url": "https://example.com/gpt5",
    "published_at": "2026-04-18T10:30:00+08:00",
    "summary": "OpenAI 于今日正式发布 GPT-5，在推理能力和多模态方面实现重大突破。",
    "importance_score": 4.5,
    "tags": ["AI", "GPT", "OpenAI"],
    "category": "AI",
    "date_partition": "2026-04-18",
}

MOCK_CONTENT_ITEM_OPENSOURCE = {
    "id": 43,
    "content_type": "text",
    "title": "Rust 2026 Edition 路线图发布",
    "source_platform": "rss-rust-blog",
    "source_url": "https://example.com/rust2026",
    "published_at": "2026-04-17T08:00:00+00:00",
    "summary": "Rust 团队公布了 2026 Edition 的完整路线图，重点改进异步生态和编译速度。",
    "importance_score": 3.0,
    "tags": ["开源", "Rust", "编程语言"],
    "category": "开源",
    "date_partition": "2026-04-17",
}

MOCK_CONTENT_ITEM_BIZ = {
    "id": 44,
    "content_type": "text",
    "title": "某初创公司完成A轮融资",
    "source_platform": "rss-36kr",
    "source_url": "https://example.com/funding",
    "published_at": "2026-04-18T14:00:00+08:00",
    "summary": "某公司完成1000万美元A轮融资。",
    "importance_score": 1.0,
    "tags": ["融资"],
    "category": "商业",
    "date_partition": "2026-04-18",
}

MOCK_CONTENT_ITEMS = [
    MOCK_CONTENT_ITEM_AI,
    MOCK_CONTENT_ITEM_OPENSOURCE,
    MOCK_CONTENT_ITEM_BIZ,
]


@pytest.fixture
def mock_materials():
    return [
        Material(
            id=42, title="OpenAI 发布 GPT-5",
            source_platform="rss-hacker-news",
            source_url="https://example.com/gpt5",
            importance_score=4.5,
            tags=["AI", "GPT", "OpenAI"],
            category="AI",
            ai_summary="OpenAI 发布 GPT-5，在推理和多模态方面实现重大突破。",
        ),
        Material(
            id=43, title="Rust 2026 Edition 路线图发布",
            source_platform="rss-rust-blog",
            source_url="https://example.com/rust2026",
            importance_score=3.0,
            tags=["开源", "Rust", "编程语言"],
            category="开源",
            ai_summary="Rust 2026 Edition 路线图聚焦异步生态和编译速度。",
        ),
        Material(
            id=44, title="某初创公司完成A轮融资",
            source_platform="rss-36kr",
            source_url="https://example.com/funding",
            importance_score=1.0,
            tags=["融资"],
            category="商业",
        ),
    ]


@pytest.fixture
def mock_personas():
    return [
        Persona(
            id="tech-reviewer", name="科技评论家",
            interests=PersonaInterests(topics=["AI", "云计算", "开源"], min_importance=3),
            style=PersonaStyle(language="zh-CN", length_preference="long"),
            system_prompt="你是一位资深科技评论家。",
        ),
        Persona(
            id="code-craftsman", name="代码匠人",
            interests=PersonaInterests(topics=["开源", "开发工具", "AI"], min_importance=2),
            style=PersonaStyle(language="zh-CN", length_preference="medium"),
            system_prompt="你是一位全栈开发者。",
        ),
    ]
