"""YAML frontmatter + Markdown body 人设加载器"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import yaml

from postmaker.core.models import Persona, PersonaInterests, PersonaStyle

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def load_persona(path: Path) -> Persona:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"Invalid persona file (missing frontmatter): {path}")

    meta = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()

    style_raw = meta.get("style", {})
    interests_raw = meta.get("interests", {})

    return Persona(
        id=meta.get("id", path.stem),
        name=meta.get("name", path.stem),
        description=meta.get("description", ""),
        style=PersonaStyle(**style_raw) if style_raw else PersonaStyle(),
        interests=PersonaInterests(**interests_raw) if interests_raw else PersonaInterests(),
        system_prompt=body,
    )


def load_all_personas(persona_dir: Path) -> List[Persona]:
    if not persona_dir.is_dir():
        return []
    personas = []
    for p in sorted(persona_dir.glob("*.yaml")):
        try:
            personas.append(load_persona(p))
        except Exception:
            continue
    return personas
