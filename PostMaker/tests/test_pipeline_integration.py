"""全管道集成测试 — Mock HTTP + Mock AI，验证各环节串联"""

import pytest
import httpx
import respx
from pathlib import Path
from unittest.mock import patch, MagicMock

from postmaker.core.models import DraftStatus, Material, PersonaInterests
from postmaker.content.generator import ContentGenerator
from postmaker.integrations.dataradar_client import DataRadarClient
from postmaker.output.markdown import save_markdown
from postmaker.output.html import save_html
from postmaker.persona.matcher import build_generation_tasks
from tests.conftest import MOCK_CONTENT_ITEMS, MOCK_CONTENT_ITEM_AI


def _make_ai_response(text: str):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = text
    return mock_resp


@respx.mock
@patch("postmaker.ai.client.completion")
@pytest.mark.asyncio
async def test_full_pipeline_trending(mock_completion, mock_materials, mock_personas, tmp_path):
    """完整流程: trending → 匹配 → 生成 → 输出"""
    respx.get("http://testserver/api/v1/content/trending").mock(
        return_value=httpx.Response(200, json={
            "items": MOCK_CONTENT_ITEMS,
            "meta": {"limit": 50, "next_cursor": None},
        })
    )

    call_count = 0
    def fake_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        title = f"生成的文章标题{call_count}"
        body = f"这是由AI生成的高质量文章正文。讨论了技术趋势和行业动态。第{call_count}篇。"
        return _make_ai_response(f"{title}\n\n{body}")
    mock_completion.side_effect = fake_completion

    client = DataRadarClient(api_base="http://testserver")
    materials = await client.get_trending(limit=10)
    await client.close()
    assert len(materials) == 3

    tasks = build_generation_tasks(materials, mock_personas)
    # A(AI,4.5): tech-reviewer✓ code-craftsman✓
    # B(开源,3.0): tech-reviewer✓ code-craftsman✓
    # C(商业,1.0): 无匹配
    assert len(tasks) == 4

    ai_config = {"model": "test", "api_key": "test", "temperature": 0.7, "max_tokens": 4000, "timeout": 30, "models": {}}
    generator = ContentGenerator(ai_config)
    drafts = await generator.generate_batch(tasks)

    completed = [d for d in drafts if d.status == DraftStatus.COMPLETED]
    assert len(completed) == 4

    base_dir = str(tmp_path)
    md_files = []
    html_files = []
    for draft in completed:
        task = next(t for t in tasks if t.material.id == draft.material_id and t.persona.id == draft.persona_id)
        md_path = save_markdown(draft, task.material, task.persona, base_dir)
        html_path = save_html(draft, task.material, task.persona, base_dir)
        md_files.append(md_path)
        html_files.append(html_path)

    assert len(md_files) == 4
    assert len(html_files) == 4

    for md in md_files:
        content = Path(md).read_text(encoding="utf-8")
        assert "---" in content
        assert "persona:" in content
        assert "生成的文章" in content or "AI生成" in content

    for html in html_files:
        content = Path(html).read_text(encoding="utf-8")
        assert "<html" in content
        assert ("科技评论家" in content or "代码匠人" in content)


@respx.mock
@patch("postmaker.ai.client.completion")
@pytest.mark.asyncio
async def test_full_pipeline_with_dedup(mock_completion, mock_personas, tmp_path):
    """去重: existing_pairs 跳过已生成组合"""
    respx.get("http://testserver/api/v1/content/trending").mock(
        return_value=httpx.Response(200, json={
            "items": MOCK_CONTENT_ITEMS[:2],
            "meta": {"limit": 50, "next_cursor": None},
        })
    )
    mock_completion.side_effect = lambda **kw: _make_ai_response("标题\n\n正文内容")

    client = DataRadarClient(api_base="http://testserver")
    materials = await client.get_trending(limit=10)
    await client.close()

    existing_pairs = {(42, "tech-reviewer")}
    tasks = build_generation_tasks(materials, mock_personas, existing_pairs)

    tech_tasks = [t for t in tasks if t.persona.id == "tech-reviewer"]
    for t in tech_tasks:
        assert t.material.id != 42


@respx.mock
@pytest.mark.asyncio
async def test_full_pipeline_dry_run(mock_materials, mock_personas):
    """dry-run 模式不调用 AI"""
    respx.get("http://testserver/api/v1/content/trending").mock(
        return_value=httpx.Response(200, json={
            "items": MOCK_CONTENT_ITEMS[:2],
            "meta": {"limit": 50, "next_cursor": None},
        })
    )

    client = DataRadarClient(api_base="http://testserver")
    materials = await client.get_trending(limit=10)
    await client.close()

    tasks = build_generation_tasks(materials, mock_personas)
    assert len(tasks) > 0
    # dry-run 只打印匹配结果，不调用 AI


@respx.mock
@patch("postmaker.ai.client.completion")
@pytest.mark.asyncio
async def test_full_pipeline_single_persona(mock_completion, mock_personas, tmp_path):
    """指定单个人设"""
    respx.get("http://testserver/api/v1/content/trending").mock(
        return_value=httpx.Response(200, json={
            "items": MOCK_CONTENT_ITEMS[:2],
            "meta": {"limit": 50, "next_cursor": None},
        })
    )
    mock_completion.side_effect = lambda **kw: _make_ai_response("标题\n\n单人设正文")

    client = DataRadarClient(api_base="http://testserver")
    materials = await client.get_trending(limit=10)
    await client.close()

    filtered_personas = [p for p in mock_personas if p.id == "tech-reviewer"]
    tasks = build_generation_tasks(materials, filtered_personas)

    for t in tasks:
        assert t.persona.id == "tech-reviewer"


@respx.mock
@patch("postmaker.ai.client.completion")
@pytest.mark.asyncio
async def test_full_pipeline_topic_bundle(mock_completion, mock_personas, tmp_path):
    """按主题获取素材包"""
    respx.get("http://testserver/api/v1/content/bundle").mock(
        return_value=httpx.Response(200, json={
            "category": "AI",
            "items": [MOCK_CONTENT_ITEM_AI],
            "total": 1,
        })
    )
    mock_completion.side_effect = lambda **kw: _make_ai_response("AI分析\n\n深度AI分析正文")

    client = DataRadarClient(api_base="http://testserver")
    materials = await client.get_bundle("AI", limit=20)
    await client.close()
    assert len(materials) == 1
    assert materials[0].category == "AI"

    tasks = build_generation_tasks(materials, mock_personas)
    assert len(tasks) > 0

    ai_config = {"model": "test", "api_key": "test", "temperature": 0.7, "max_tokens": 4000, "timeout": 30, "models": {}}
    generator = ContentGenerator(ai_config)
    drafts = await generator.generate_batch(tasks)
    completed = [d for d in drafts if d.status == DraftStatus.COMPLETED]
    assert len(completed) == len(tasks)
