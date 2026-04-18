CREATE SCHEMA IF NOT EXISTS postmaker;

CREATE TABLE IF NOT EXISTS postmaker.materials (
    id BIGSERIAL PRIMARY KEY,
    dataradar_id BIGINT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source_platform TEXT,
    source_url TEXT,
    published_at TIMESTAMPTZ,
    summary TEXT,
    full_text TEXT,
    importance_score FLOAT DEFAULT 0.0,
    tags TEXT[],
    category TEXT,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS postmaker.drafts (
    id BIGSERIAL PRIMARY KEY,
    material_id BIGINT NOT NULL REFERENCES postmaker.materials(id),
    persona_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'completed',
    model_used TEXT,
    output_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (material_id, persona_id)
);
