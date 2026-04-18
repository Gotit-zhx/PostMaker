"""Prompt 组装器"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from postmaker.core.models import GenerationTask

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts" / "generate"

_LENGTH_MAP = {
    "short": "800-1200字",
    "medium": "1500-2500字",
    "long": "3000-5000字",
}


def build_messages(task: GenerationTask) -> List[Dict[str, str]]:
    system_prompt, user_template = _load_template()

    material = task.material
    persona = task.persona

    content_for_prompt = material.ai_summary or material.summary or ""
    full_text_section = ""
    if material.full_text and len(content_for_prompt) < 100:
        full_text_section = f"\n全文：\n{material.full_text[:3000]}"

    system = system_prompt.replace("{persona_system_prompt}", persona.system_prompt)

    user = user_template.format(
        title=material.title,
        source=material.source_platform,
        published_at=str(material.published_at or ""),
        summary=content_for_prompt,
        full_text_section=full_text_section,
        language=persona.style.language,
        length_preference=_LENGTH_MAP.get(persona.style.length_preference, "1500-2500字"),
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _load_template() -> Tuple[str, str]:
    path = _PROMPT_DIR / "content_prompt.txt"
    if not path.exists():
        return "", ""
    content = path.read_text(encoding="utf-8")
    if "[system]" in content and "[user]" in content:
        parts = content.split("[user]")
        system = parts[0].split("[system]")[1].strip() if "[system]" in parts[0] else ""
        user = parts[1].strip() if len(parts) > 1 else ""
        return system, user
    return "", content
