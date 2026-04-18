"""内容生成器测试"""

import pytest
from unittest.mock import patch, MagicMock

from postmaker.core.models import (
    Draft,
    DraftStatus,
    GenerationTask,
    Material,
    Persona,
    PersonaInterests,
    PersonaStyle,
)
from postmaker.content.generator import ContentGenerator, _parse_output


@pytest.fixture
def ai_config():
    return {
        "model": "test-model",
        "api_key": "test-key",
        "temperature": 0.7,
        "max_tokens": 4000,
        "timeout": 30,
        "models": {"high": "high-model", "medium": ""},
    }


@pytest.fixture
def task():
    return GenerationTask(
        material=Material(
            id=1, title="测试素材标题",
            source_platform="rss-test",
            ai_summary="这是一篇关于AI技术的测试摘要。",
            importance_score=3.5,
            tags=["AI"],
            category="AI",
        ),
        persona=Persona(
            id="test-persona", name="测试人设",
            style=PersonaStyle(language="zh-CN", length_preference="medium"),
            system_prompt="你是测试人设。",
            interests=PersonaInterests(topics=["AI"], min_importance=2),
        ),
    )


@pytest.fixture
def high_importance_task():
    return GenerationTask(
        material=Material(
            id=2, title="重要素材",
            source_platform="rss-test",
            ai_summary="重要新闻摘要",
            importance_score=4.5,
            tags=["AI"],
            category="AI",
        ),
        persona=Persona(
            id="test-persona", name="测试人设",
            style=PersonaStyle(language="zh-CN"),
            system_prompt="你是测试人设。",
            interests=PersonaInterests(topics=["AI"], min_importance=2),
        ),
    )


def test_parse_output_normal():
    title, body = _parse_output("AI 技术革命\n\n这是正文第一段。\n\n这是第二段。")
    assert title == "AI 技术革命"
    assert "正文第一段" in body


def test_parse_output_strips_heading():
    title, body = _parse_output("# AI 技术革命\n\n正文内容")
    assert title == "AI 技术革命"


def test_parse_output_single_line():
    title, body = _parse_output("只有一行")
    assert title == ""
    assert body == "只有一行"


@patch("postmaker.content.generator.ContentGenerator._generate_one")
@pytest.mark.asyncio
async def test_generate_batch_concurrency(mock_gen, ai_config, task):
    mock_gen.return_value = Draft(
        material_id=1, persona_id="test-persona",
        title="生成的标题", body="生成的正文",
        status=DraftStatus.COMPLETED, model_used="test-model",
    )
    gen = ContentGenerator(ai_config)
    tasks = [task] * 5
    drafts = await gen.generate_batch(tasks)
    assert len(drafts) == 5
    assert all(d.status == DraftStatus.COMPLETED for d in drafts)


@patch("postmaker.content.generator.ContentGenerator._generate_one")
@pytest.mark.asyncio
async def test_generate_batch_handles_exception(mock_gen, ai_config, task):
    mock_gen.side_effect = RuntimeError("AI service down")
    gen = ContentGenerator(ai_config)
    drafts = await gen.generate_batch([task])
    assert len(drafts) == 1
    assert drafts[0].status == DraftStatus.FAILED


@patch("postmaker.ai.client.completion")
def test_generate_one_success(mock_completion, ai_config, task):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "AI改变世界\n\n这是一篇关于AI的深度分析文章。"
    mock_completion.return_value = mock_response

    gen = ContentGenerator(ai_config)
    draft = gen._generate_one(task)
    assert draft.status == DraftStatus.COMPLETED
    assert draft.title == "AI改变世界"
    assert "深度分析" in draft.body
    assert draft.model_used == "test-model"


@patch("postmaker.ai.client.completion")
def test_generate_one_empty_response(mock_completion, ai_config, task):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = ""
    mock_completion.return_value = mock_response

    gen = ContentGenerator(ai_config)
    draft = gen._generate_one(task)
    assert draft.status == DraftStatus.FAILED


@patch("postmaker.ai.client.completion")
def test_model_routing_high_importance(mock_completion, ai_config, high_importance_task):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "标题\n\n正文"
    mock_completion.return_value = mock_response

    gen = ContentGenerator(ai_config)
    gen._generate_one(high_importance_task)
    call_kwargs = mock_completion.call_args
    assert call_kwargs.kwargs.get("model") == "high-model" or call_kwargs[1].get("model") == "high-model"


@patch("postmaker.ai.client.completion")
def test_generate_with_refine(mock_completion, ai_config, task):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "标题\n\n初稿正文"
    mock_completion.return_value = mock_response

    gen = ContentGenerator(ai_config, refine_enabled=True)
    draft = gen._generate_one(task)
    assert draft.status == DraftStatus.COMPLETED
    assert mock_completion.call_count == 2
