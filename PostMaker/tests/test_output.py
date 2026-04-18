"""双格式输出测试"""

from postmaker.core.models import Draft, Material, Persona, PersonaStyle
from postmaker.output.markdown import save_markdown
from postmaker.output.html import save_html


def _draft():
    return Draft(
        material_id=1, persona_id="tech",
        title="测试文章标题",
        body="## 正文\n\n这是一篇测试文章。\n\n- 要点一\n- 要点二\n",
        model_used="test-model",
    )


def _material():
    return Material(
        id=1, title="原始素材", source_platform="rss-test",
        source_url="https://example.com/article",
    )


def _persona():
    return Persona(
        id="tech", name="科技评论家",
        style=PersonaStyle(language="zh-CN"),
    )


def test_save_markdown(tmp_path):
    path = save_markdown(_draft(), _material(), _persona(), str(tmp_path))
    assert path.endswith(".md")
    content = open(path, encoding="utf-8").read()
    assert "---" in content
    assert "persona: tech" in content
    assert "测试文章" in content


def test_save_html(tmp_path):
    path = save_html(_draft(), _material(), _persona(), str(tmp_path))
    assert path.endswith(".html")
    content = open(path, encoding="utf-8").read()
    assert "<html" in content
    assert "测试文章" in content
    assert "科技评论家" in content
    assert "<li>" in content
