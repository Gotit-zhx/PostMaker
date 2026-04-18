"""PostMaker CRUD"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from postmaker.core.models import Draft, DraftStatus, Material


class PostMakerRepository:
    def __init__(self, pool):
        self._pool = pool

    async def ensure_schema(self) -> None:
        from pathlib import Path
        sql_path = Path(__file__).parent / "schema.sql"
        sql = sql_path.read_text(encoding="utf-8")
        async with self._pool.acquire() as conn:
            await conn.execute(sql)

    async def upsert_material(self, material: Material) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO postmaker.materials (
                    dataradar_id, title, source_platform, source_url,
                    published_at, summary, full_text,
                    importance_score, tags, category
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (dataradar_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    summary = COALESCE(EXCLUDED.summary, postmaker.materials.summary),
                    importance_score = GREATEST(EXCLUDED.importance_score, postmaker.materials.importance_score)
                RETURNING id
                """,
                material.id,
                material.title,
                material.source_platform,
                material.source_url,
                material.published_at,
                material.ai_summary or material.summary,
                material.full_text,
                material.importance_score,
                material.tags or [],
                material.category,
            )
        return row["id"]

    async def save_draft(self, draft: Draft, local_material_id: int) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO postmaker.drafts (
                    material_id, persona_id, title, body,
                    status, model_used, output_path
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (material_id, persona_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    body = EXCLUDED.body,
                    status = EXCLUDED.status,
                    model_used = EXCLUDED.model_used,
                    output_path = EXCLUDED.output_path,
                    created_at = NOW()
                RETURNING id
                """,
                local_material_id,
                draft.persona_id,
                draft.title,
                draft.body,
                draft.status.value,
                draft.model_used,
                draft.output_path,
            )
        return row["id"]

    async def get_existing_pairs(self) -> Set[Tuple[int, str]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.dataradar_id, d.persona_id
                FROM postmaker.drafts d
                JOIN postmaker.materials m ON m.id = d.material_id
                WHERE d.status = 'completed'
                """
            )
        return {(r["dataradar_id"], r["persona_id"]) for r in rows}

    async def list_drafts(
        self,
        persona_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        async with self._pool.acquire() as conn:
            if persona_id:
                rows = await conn.fetch(
                    """
                    SELECT d.*, m.title as material_title, m.source_url
                    FROM postmaker.drafts d
                    JOIN postmaker.materials m ON m.id = d.material_id
                    WHERE d.persona_id = $1
                    ORDER BY d.created_at DESC LIMIT $2
                    """,
                    persona_id, limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT d.*, m.title as material_title, m.source_url
                    FROM postmaker.drafts d
                    JOIN postmaker.materials m ON m.id = d.material_id
                    ORDER BY d.created_at DESC LIMIT $1
                    """,
                    limit,
                )
        return [dict(r) for r in rows]
