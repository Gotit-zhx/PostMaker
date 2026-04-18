"""人设加载器测试"""

from pathlib import Path

import pytest

from postmaker.persona.loader import load_persona, load_all_personas


@pytest.fixture
def persona_dir():
    return Path(__file__).parent.parent / "config" / "personas"


def test_load_tech_reviewer(persona_dir):
    path = persona_dir / "tech-reviewer.yaml"
    p = load_persona(path)
    assert p.id == "tech-reviewer"
    assert p.name == "科技评论家"
    assert p.style.language == "zh-CN"
    assert p.style.length_preference == "long"
    assert "AI" in p.interests.topics
    assert p.interests.min_importance == 3
    assert "科技评论家" in p.system_prompt


def test_load_code_craftsman(persona_dir):
    path = persona_dir / "code-craftsman.yaml"
    p = load_persona(path)
    assert p.id == "code-craftsman"
    assert p.interests.min_importance == 2
    assert "开源" in p.interests.topics


def test_load_all_personas(persona_dir):
    personas = load_all_personas(persona_dir)
    assert len(personas) >= 2
    ids = {p.id for p in personas}
    assert "tech-reviewer" in ids
    assert "code-craftsman" in ids


def test_load_invalid_file(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("no frontmatter here", encoding="utf-8")
    with pytest.raises(ValueError, match="missing frontmatter"):
        load_persona(bad)


def test_load_empty_dir(tmp_path):
    assert load_all_personas(tmp_path) == []
