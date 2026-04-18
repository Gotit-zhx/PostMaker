"""素材-人设匹配引擎"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from postmaker.core.models import GenerationTask, Material, Persona


def match_material_to_personas(
    material: Material, personas: List[Persona]
) -> List[Persona]:
    matched = []
    for persona in personas:
        interests = persona.interests
        if material.importance_score < interests.min_importance:
            continue
        if not interests.topics:
            matched.append(persona)
            continue
        topics_lower = {t.lower() for t in interests.topics}
        material_topics = _extract_topics(material)
        if topics_lower & material_topics:
            matched.append(persona)
    return matched


def build_generation_tasks(
    materials: List[Material],
    personas: List[Persona],
    existing_pairs: Set[Tuple[int, str]] | None = None,
) -> List[GenerationTask]:
    existing = existing_pairs or set()
    tasks = []
    for material in materials:
        matched = match_material_to_personas(material, personas)
        for persona in matched:
            if (material.id, persona.id) in existing:
                continue
            tasks.append(GenerationTask(material=material, persona=persona))
    return tasks


def _extract_topics(material: Material) -> set[str]:
    topics: set[str] = set()
    if material.category:
        topics.add(material.category.lower())
    for tag in material.tags:
        topics.add(tag.lower())
    return topics
