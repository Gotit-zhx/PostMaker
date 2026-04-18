"""人设匹配引擎测试"""

from postmaker.core.models import Material, Persona, PersonaInterests, PersonaStyle
from postmaker.persona.matcher import (
    build_generation_tasks,
    match_material_to_personas,
)


def _persona(pid, topics, min_imp=0):
    return Persona(
        id=pid, name=pid,
        interests=PersonaInterests(topics=topics, min_importance=min_imp),
    )


def test_match_by_category():
    m = Material(id=1, title="Test", category="AI", importance_score=3)
    p = _persona("tech", ["AI"], min_imp=2)
    assert match_material_to_personas(m, [p]) == [p]


def test_match_by_tag():
    m = Material(id=1, title="Test", tags=["开源"], importance_score=3)
    p = _persona("dev", ["开源"])
    assert match_material_to_personas(m, [p]) == [p]


def test_no_match_importance_too_low():
    m = Material(id=1, title="Test", category="AI", importance_score=1)
    p = _persona("tech", ["AI"], min_imp=3)
    assert match_material_to_personas(m, [p]) == []


def test_no_match_topic_mismatch():
    m = Material(id=1, title="Test", category="硬件", importance_score=5)
    p = _persona("tech", ["AI", "云计算"])
    assert match_material_to_personas(m, [p]) == []


def test_match_empty_topics_matches_all():
    m = Material(id=1, title="Test", importance_score=1)
    p = _persona("general", [])
    assert match_material_to_personas(m, [p]) == [p]


def test_build_tasks_dedup():
    m = Material(id=1, title="Test", category="AI", importance_score=3)
    p = _persona("tech", ["AI"])
    existing = {(1, "tech")}
    tasks = build_generation_tasks([m], [p], existing)
    assert len(tasks) == 0


def test_build_tasks_no_existing():
    m = Material(id=1, title="Test", category="AI", importance_score=3)
    p = _persona("tech", ["AI"])
    tasks = build_generation_tasks([m], [p])
    assert len(tasks) == 1
    assert tasks[0].material.id == 1
    assert tasks[0].persona.id == "tech"
