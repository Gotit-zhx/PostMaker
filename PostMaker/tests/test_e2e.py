"""E2E 端到端测试 — 需要 Docker 基础设施 + AI API

运行方式:
    AI_API_KEY=... AI_MODEL=... uv run pytest tests/test_e2e.py -v -m e2e
"""

import os
from pathlib import Path

import pytest

from postmaker.core.config import get_persona_dir, load_config
from postmaker.core.models import DraftStatus
from postmaker.content.generator import ContentGenerator
from postmaker.integrations.dataradar_client import DataRadarClient
from postmaker.output.html import save_html
from postmaker.output.markdown import save_markdown
from postmaker.persona.loader import load_all_personas
from postmaker.persona.matcher import build_generation_tasks

pytestmark = pytest.mark.e2e

_SKIP_REASON = "E2E: 需要 AI_API_KEY 和运行中的 DataRadar API"


def _should_skip():
    if not os.environ.get("AI_API_KEY"):
        return True
    if not os.environ.get("AI_MODEL"):
        return True
    return False


@pytest.mark.skipif(_should_skip(), reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_e2e_fetch_materials():
    """验证能从 DataRadar API 获取素材"""
    cfg = load_config()
    dr_cfg = cfg.get("dataradar", {})
    client = DataRadarClient(
        api_base=dr_cfg.get("api_base", "http://localhost:8000"),
        timeout=dr_cfg.get("timeout", 15),
    )
    try:
        materials = await client.list_content(limit=5)
        assert len(materials) > 0
        m = materials[0]
        assert m.id > 0
        assert m.title
        assert m.source_platform
    finally:
        await client.close()


@pytest.mark.skipif(_should_skip(), reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_e2e_generate_from_trending(tmp_path):
    """完整 E2E：trending → 匹配 → AI 生成 → 文件输出"""
    cfg = load_config()
    dr_cfg = cfg.get("dataradar", {})
    ai_cfg = cfg.get("ai", {})

    ai_cfg["api_key"] = os.environ.get("AI_API_KEY", ai_cfg.get("api_key", ""))
    ai_cfg["model"] = os.environ.get("AI_MODEL", ai_cfg.get("model", ""))
    ai_cfg["api_base"] = os.environ.get("AI_API_BASE", ai_cfg.get("api_base", ""))

    client = DataRadarClient(
        api_base=dr_cfg.get("api_base", "http://localhost:8000"),
        timeout=dr_cfg.get("timeout", 15),
    )
    try:
        materials = await client.get_trending(limit=3)
    finally:
        await client.close()

    if not materials:
        pytest.skip("DataRadar API 无数据")

    personas = load_all_personas(get_persona_dir(cfg))
    if not personas:
        pytest.skip("未找到人设文件")

    tasks = build_generation_tasks(materials, personas)
    if not tasks:
        pytest.skip("无匹配任务")

    tasks = tasks[:2]

    generator = ContentGenerator(ai_cfg, refine_enabled=False)
    drafts = await generator.generate_batch(tasks)

    completed = [d for d in drafts if d.status == DraftStatus.COMPLETED]
    assert len(completed) > 0, f"所有生成均失败: {[d.status for d in drafts]}"

    base_dir = str(tmp_path)
    for draft in completed:
        task = next(t for t in tasks if t.material.id == draft.material_id and t.persona.id == draft.persona_id)

        md_path = save_markdown(draft, task.material, task.persona, base_dir)
        html_path = save_html(draft, task.material, task.persona, base_dir)

        md_content = Path(md_path).read_text(encoding="utf-8")
        assert "---" in md_content
        assert draft.title in md_content or task.material.title in md_content
        assert len(md_content) > 200

        html_content = Path(html_path).read_text(encoding="utf-8")
        assert "<html" in html_content
        assert task.persona.name in html_content
        assert len(html_content) > 300
