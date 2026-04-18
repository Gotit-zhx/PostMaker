"""数据模型测试"""

from postmaker.core.models import (
    Draft, DraftStatus, GenerationTask, Material,
    Persona, PersonaInterests, PersonaStyle,
)


def test_material_defaults():
    m = Material(id=1, title="Test")
    assert m.importance_score == 0.0
    assert m.tags == []
    assert m.category is None


def test_persona_style_defaults():
    s = PersonaStyle()
    assert s.tone == "professional"
    assert s.language == "zh-CN"
    assert s.length_preference == "medium"


def test_draft_status():
    d = Draft(material_id=1, persona_id="test")
    assert d.status == DraftStatus.COMPLETED


def test_generation_task():
    m = Material(id=1, title="Test Article")
    p = Persona(id="tech", name="Tech")
    t = GenerationTask(material=m, persona=p)
    assert t.material.id == 1
    assert t.persona.id == "tech"
