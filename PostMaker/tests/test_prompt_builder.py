"""Prompt 构建器测试"""

from postmaker.core.models import GenerationTask, Material, Persona, PersonaStyle
from postmaker.content.prompt_builder import build_messages


def test_build_messages_basic():
    m = Material(
        id=1, title="GPT-5 发布", source_platform="rss-openai",
        ai_summary="OpenAI 发布了 GPT-5...", importance_score=4,
    )
    p = Persona(
        id="tech", name="科技评论家",
        style=PersonaStyle(language="zh-CN", length_preference="long"),
        system_prompt="你是一位科技评论家。",
    )
    task = GenerationTask(material=m, persona=p)
    msgs = build_messages(task)

    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "科技评论家" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert "GPT-5" in msgs[1]["content"]
    assert "3000-5000字" in msgs[1]["content"]


def test_build_messages_uses_summary_over_fulltext():
    m = Material(
        id=1, title="Test", ai_summary="This is a long enough summary " * 10,
        full_text="Full text here " * 100,
    )
    p = Persona(id="dev", name="Dev")
    task = GenerationTask(material=m, persona=p)
    msgs = build_messages(task)
    assert "全文" not in msgs[1]["content"]


def test_build_messages_falls_back_to_fulltext():
    m = Material(id=1, title="Test", full_text="Full text content here.")
    p = Persona(id="dev", name="Dev")
    task = GenerationTask(material=m, persona=p)
    msgs = build_messages(task)
    assert "全文" in msgs[1]["content"]
