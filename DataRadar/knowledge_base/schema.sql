-- ================================================================
-- DataRadar Knowledge Base Schema
-- PostgreSQL 16 + pgvector + pg_trgm
--
-- 用途：多模态内容统一存储，支持数千智能体并发查询
-- 初始化：在 docker-compose 启动时自动执行
-- ================================================================

-- 必要扩展
CREATE EXTENSION IF NOT EXISTS vector;    -- 向量搜索
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- 字符串相似度（支持中英文）


-- ================================================================
-- 1. 核心内容表：多模态统一存储
-- ================================================================
CREATE TABLE IF NOT EXISTS content_items (
    id              BIGSERIAL PRIMARY KEY,

    -- 内容类型
    content_type    TEXT NOT NULL DEFAULT 'text'
                    CHECK (content_type IN ('text', 'video', 'audio', 'image')),

    -- 来源信息
    title           TEXT NOT NULL,
    source_platform TEXT NOT NULL,    -- hn, reddit, youtube, techcrunch, rss-xxx, etc.
    source_url      TEXT,
    canonical_url   TEXT,             -- 去重用规范 URL

    -- 时间
    published_at    TIMESTAMPTZ,
    crawled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    date_partition  DATE NOT NULL,    -- 按日分区键（便于按天查询和清理）

    -- 文本内容
    summary         TEXT,             -- 摘要（RSS summary / 视频 description 前 500 字）
    full_text       TEXT,             -- 全文（Trafilatura/Jina 提取，播客字幕等）

    -- 媒体字段（视频 / 音频）
    thumbnail_url   TEXT,             -- 封面图 URL
    media_url       TEXT,             -- 播客音频直链 / 视频文件 URL
    duration_sec    INTEGER,          -- 时长（秒）
    image_urls      TEXT[],           -- 文章内图片 URL 列表

    -- 采集元数据（DataRadar 直写）
    author          TEXT,
    ai_summary      TEXT,                 -- AI 生成的结构化摘要
    feed_id         TEXT,                 -- RSS 源 ID
    feed_name       TEXT,                 -- RSS 源名称
    crawl_count     INTEGER DEFAULT 1,    -- 累计采集次数
    first_crawl_at  TIMESTAMPTZ,          -- 首次采集时间
    last_crawl_at   TIMESTAMPTZ,          -- 最近采集时间

    -- 分析字段
    importance_score FLOAT DEFAULT 0.0,
    tags            TEXT[],
    category        TEXT,
    raw_metadata    JSONB DEFAULT '{}',

    -- 向量（pgvector）
    embedding       vector(1536),

    -- 去重
    content_hash    TEXT,

    -- 约束
    UNIQUE (source_platform, source_url)
);

-- 索引：时间分区（最常用过滤条件）
CREATE INDEX IF NOT EXISTS idx_ci_date
    ON content_items (date_partition DESC);

-- 索引：类型 + 日期（按类型查询时使用）
CREATE INDEX IF NOT EXISTS idx_ci_type_date
    ON content_items (content_type, date_partition DESC);

-- 索引：重要性（热点排序）
CREATE INDEX IF NOT EXISTS idx_ci_importance
    ON content_items (importance_score DESC, date_partition DESC);

-- 索引：标签 GIN（WHERE tags @> ARRAY['AI']）
CREATE INDEX IF NOT EXISTS idx_ci_tags
    ON content_items USING GIN (tags);

-- 索引：平台 + 日期
CREATE INDEX IF NOT EXISTS idx_ci_platform
    ON content_items (source_platform, date_partition DESC);

-- 索引：标题三元组相似度（中英文全文搜索）
CREATE INDEX IF NOT EXISTS idx_ci_title_trgm
    ON content_items USING GIN (title gin_trgm_ops);

-- 索引：全文三元组（仅有 full_text 的行）
CREATE INDEX IF NOT EXISTS idx_ci_text_trgm
    ON content_items USING GIN (full_text gin_trgm_ops)
    WHERE full_text IS NOT NULL;

-- 索引：向量（IVFFlat，近似搜索，比精确搜索快 10-100x）
-- lists = sqrt(行数)；10万行建议 100-200
CREATE INDEX IF NOT EXISTS idx_ci_embedding
    ON content_items USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
    WHERE embedding IS NOT NULL;


-- ================================================================
-- 2. 知识条目表：跨平台聚合去重后的事件/话题
-- ================================================================
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id              BIGSERIAL PRIMARY KEY,

    canonical_title TEXT NOT NULL,        -- 代表性标题（最权威来源的标题）
    summary         TEXT,                 -- AI 生成摘要
    full_text       TEXT,                 -- 最完整的全文
    category        TEXT,
    tags            TEXT[],
    image_urls      TEXT[],
    importance_score FLOAT DEFAULT 0.0,
    embedding       vector(1536),

    first_seen_at   TIMESTAMPTZ NOT NULL,
    last_seen_at    TIMESTAMPTZ NOT NULL,
    source_count    INTEGER DEFAULT 1,    -- 报道此事件的平台数量

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ke_date
    ON knowledge_entries (first_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_ke_importance
    ON knowledge_entries (importance_score DESC);

CREATE INDEX IF NOT EXISTS idx_ke_tags
    ON knowledge_entries USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_ke_embedding
    ON knowledge_entries USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50)
    WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ke_title_trgm
    ON knowledge_entries USING GIN (canonical_title gin_trgm_ops);


-- ================================================================
-- 3. 聚合关系表：knowledge_entry ↔ content_items
-- ================================================================
CREATE TABLE IF NOT EXISTS knowledge_content_map (
    knowledge_id    BIGINT NOT NULL REFERENCES knowledge_entries(id) ON DELETE CASCADE,
    content_id      BIGINT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    PRIMARY KEY (knowledge_id, content_id)
);

CREATE INDEX IF NOT EXISTS idx_kcm_content
    ON knowledge_content_map (content_id);


-- ================================================================
-- 4. ETL 追踪表：记录同步状态
-- ================================================================
CREATE TABLE IF NOT EXISTS etl_sync_records (
    id              BIGSERIAL PRIMARY KEY,
    date_partition  DATE NOT NULL,
    source_type     TEXT NOT NULL,
    synced_at       TIMESTAMPTZ DEFAULT NOW(),
    item_count      INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'success',
    error_message   TEXT,
    UNIQUE (date_partition, source_type)
);


-- ================================================================
-- 5. 素材使用标记表：PostMaker 人设使用追踪
-- ================================================================
CREATE TABLE IF NOT EXISTS content_usage_marks (
    content_id      BIGINT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    persona_id      TEXT NOT NULL,
    marked_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (content_id, persona_id)
);

CREATE INDEX IF NOT EXISTS idx_cum_persona
    ON content_usage_marks (persona_id, marked_at DESC);


-- ================================================================
-- 自动更新 knowledge_entries.updated_at 触发器
-- ================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ke_updated_at
    BEFORE UPDATE ON knowledge_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ================================================================
-- 迁移：为已有数据库添加新列（IF NOT EXISTS 保证幂等）
-- ================================================================
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS author TEXT;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS feed_id TEXT;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS feed_name TEXT;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS crawl_count INTEGER DEFAULT 1;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS first_crawl_at TIMESTAMPTZ;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS last_crawl_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_ci_feed_id
    ON content_items (feed_id, date_partition DESC)
    WHERE feed_id IS NOT NULL;
