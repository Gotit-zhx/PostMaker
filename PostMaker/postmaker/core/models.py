"""PostMaker 数据模型"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Material(BaseModel):
    id: int
    title: str
    source_platform: str = ""
    source_url: str = ""
    thumbnail_url: str = ""
    media_url: str = ""
    image_urls: List[str] = Field(default_factory=list)
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    full_text: Optional[str] = None
    importance_score: float = 0.0
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    ai_summary: Optional[str] = None


class PersonaStyle(BaseModel):
    tone: str = "professional"
    language: str = "zh-CN"
    length_preference: str = "medium"


class PersonaInterests(BaseModel):
    topics: List[str] = Field(default_factory=list)
    min_importance: float = 0.0


class Persona(BaseModel):
    id: str
    name: str
    description: str = ""
    style: PersonaStyle = Field(default_factory=PersonaStyle)
    system_prompt: str = ""
    interests: PersonaInterests = Field(default_factory=PersonaInterests)


class DraftStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Draft(BaseModel):
    id: Optional[int] = None
    material_id: int
    persona_id: str
    title: str = ""
    body: str = ""
    status: DraftStatus = DraftStatus.COMPLETED
    model_used: str = ""
    output_path: Optional[str] = None
    created_at: Optional[datetime] = None


class GenerationTask(BaseModel):
    material: Material
    persona: Persona
