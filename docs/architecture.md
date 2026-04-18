# 系统架构

## 全局数据流

```
RSS 源（15+）─────────────────┐
  直接 RSS + RSSHub 代理      │
                              ├─→ 全文提取 ─→ AI 结构化摘要 ─→ PostgreSQL 直写
Playwright 网页采集（可选）────┘                                       │
                                                                后处理（可选）
                                                            embedding + 聚合
                                                                      │
                                                                Redis 缓存
                                                                      │
                                                              FastAPI REST API
                                                                      │
                                                                 PostMaker
                                                           ┌──────────┴──────────┐
                                                      科技评论家             代码匠人
                                                      深度长文               实操分享
                                                           │                   │
                                                       .md + .html         .md + .html
```

系统分为两个独立项目：

- **DataRadar**：数据采集与知识库，负责从外部源获取素材、AI 分析、存储和检索
- **PostMaker**：内容生成系统，通过 REST API 消费 DataRadar 数据，多人设生成差异化内容

两者通过 DataRadar 的 REST API（默认 `http://localhost:8000`）解耦通信。

---

## DataRadar 架构

### 采集管道（5 阶段 + 后处理）

```
DataCollector.run()
    │
    ├─ ① _fetch_rss()
    │     RSSFetcher（feedparser）→ 解析所有 RSS 源
    │     全量入库，不做过滤
    │
    ├─ ② _fetch_web_pages()（可选）
    │     PlaywrightScraper → JS 渲染网页采集
    │     支持 CSS 选择器配置（list/title/link selector）
    │
    ├─ ③ _enrich_full_text()
    │     ArticleExtractor 三引擎回退：
    │     Trafilatura (20并发) → Playwright (3页面) → Jina Reader (5并发)
    │     最小文本长度 200 字符
    │
    ├─ ④ _generate_summaries()
    │     ContentSummarizer → LLM JSON 结构化输出
    │     {summary, category, tags, importance}
    │     智能截断（1500字符）+ 规则预判跳过
    │     并发限制：Semaphore(10)
    │
    ├─ ⑤ save_rss_data()
    │     StorageManager → asyncpg UPSERT 直写
    │     去重键：(source_platform, source_url)
    │     ON CONFLICT: 递增 crawl_count, COALESCE 保留非空字段
    │
    └─ ⑥ _run_post_processing()（可选）
          ETLPipeline:
          ├─ _embed_missing()  → 生成 pgvector embedding
          ├─ _aggregate()      → 跨平台标题去重聚合 → knowledge_entries
          └─ _invalidate_cache() → 清除 Redis 缓存
```

### 检索层

```
客户端请求
    │
    ├─ Redis 缓存 ← 命中则直接返回（TTL 300s / 1800s）
    │
    └─ PostgreSQL 查询
         ├─ 全文搜索 → pg_trgm（三元组相似度）
         ├─ 语义搜索 → pgvector（余弦相似度，1536 维）
         ├─ 热点排行 → importance_score DESC
         ├─ 分类趋势 → GROUP BY category
         └─ 素材包   → WHERE category = ?
```

---

## PostMaker 架构

### 生成管道

```
cmd_generate(args)
    │
    ├─ 1. 加载配置 + 人设
    │     config/config.yaml + config/personas/*.yaml
    │     PersonaLoader → YAML frontmatter + Markdown body
    │
    ├─ 2. DataRadarClient 获取素材
    │     ├─ --material-id → get_content_detail(id)
    │     ├─ --topic       → get_bundle(category)
    │     ├─ --trending    → get_trending(date)
    │     └─ 默认          → list_content(date, limit)
    │
    ├─ 3. [可选] 加载已生成记录（PostgreSQL 去重）
    │     PostMakerRepository.get_existing_pairs()
    │
    ├─ 4. build_generation_tasks()
    │     素材 × 匹配人设 → 任务列表
    │     匹配规则：importance >= min_importance AND topics 交集
    │     跳过 existing_pairs 中已有组合
    │
    ├─ 5. [dry-run?] 打印匹配结果并退出
    │
    ├─ 6. generate_batch(tasks)
    │     asyncio.Semaphore(5) 并发生成
    │     ├─ build_messages(task) → system + user prompt
    │     ├─ AIClient.chat()     → LLM 生成
    │     │   模型路由：importance ≥ 4 → models.high
    │     │             其余 → models.medium 或默认
    │     └─ [refine] → 可选二阶段优化（最多 1 轮）
    │
    ├─ 7. 保存 .md + .html
    │     output/{date}/{persona_id}/{slug}.md|html
    │
    └─ 8. [可选] 写入 PostgreSQL
          PostMakerRepository.upsert_material() + save_draft()
```

### 人设匹配引擎

```python
match_material_to_personas(material, personas):
    # importance >= persona.interests.min_importance
    # AND (persona.interests.topics 交集 material.tags/category 非空
    #      OR persona.interests.topics 为空 → 匹配所有)

build_generation_tasks(materials, personas, existing_pairs):
    # 遍历所有 material × persona 组合
    # 过滤已匹配 + 跳过已生成 → GenerationTask 列表
```

---

## 数据库设计

两个项目共用同一个 PostgreSQL 实例，使用不同的 schema 隔离。

### DataRadar 表（public schema）

#### content_items — 采集内容主表

```sql
id                BIGSERIAL PRIMARY KEY
content_type      TEXT          -- text, video, audio, image
title             TEXT NOT NULL
source_platform   TEXT NOT NULL -- rss-{feed_id}, reddit, hn 等
source_url        TEXT          -- 原文 URL
canonical_url     TEXT          -- 规范化 URL
published_at      TIMESTAMPTZ
crawled_at        TIMESTAMPTZ DEFAULT NOW()
date_partition    DATE NOT NULL -- 日期分区键
summary           TEXT          -- RSS 原始摘要
full_text         TEXT          -- 全文提取结果
ai_summary        TEXT          -- AI 生成摘要
feed_id           TEXT
feed_name         TEXT
crawl_count       INTEGER DEFAULT 1
importance_score  FLOAT DEFAULT 0.0
tags              TEXT[]        -- AI 提取标签
category          TEXT          -- AI 分类
embedding         vector(1536)  -- pgvector 语义搜索
content_hash      TEXT          -- MD5(platform:url)

UNIQUE (source_platform, source_url)
```

索引：date_partition, importance_score, tags (GIN), title (pg_trgm), embedding (IVFFlat)

#### knowledge_entries — 跨平台知识聚合

```sql
id                BIGSERIAL PRIMARY KEY
canonical_title   TEXT NOT NULL
summary           TEXT
category          TEXT
tags              TEXT[]
importance_score  FLOAT DEFAULT 0.0
embedding         vector(1536)
source_count      INTEGER DEFAULT 1   -- 多少个平台报道
first_seen_at     TIMESTAMPTZ
last_seen_at      TIMESTAMPTZ
```

#### knowledge_content_map — 知识-内容关联

```sql
knowledge_id  BIGINT REFERENCES knowledge_entries(id) ON DELETE CASCADE
content_id    BIGINT REFERENCES content_items(id) ON DELETE CASCADE
PRIMARY KEY (knowledge_id, content_id)
```

#### content_usage_marks — PostMaker 使用标记

```sql
content_id    BIGINT REFERENCES content_items(id) ON DELETE CASCADE
persona_id    TEXT NOT NULL
marked_at     TIMESTAMPTZ DEFAULT NOW()
UNIQUE (content_id, persona_id)
```

#### etl_sync_records — ETL 进度追踪

```sql
id              BIGSERIAL PRIMARY KEY
date_partition  DATE NOT NULL
source_type     TEXT NOT NULL
item_count      INTEGER DEFAULT 0
status          TEXT DEFAULT 'success'
UNIQUE (date_partition, source_type)
```

### PostMaker 表（postmaker schema）

#### postmaker.materials — 素材本地副本

```sql
id                BIGSERIAL PRIMARY KEY
dataradar_id      BIGINT NOT NULL UNIQUE
title             TEXT NOT NULL
source_platform   TEXT
source_url        TEXT
published_at      TIMESTAMPTZ
summary           TEXT
full_text         TEXT
importance_score  FLOAT DEFAULT 0.0
tags              TEXT[]
category          TEXT
fetched_at        TIMESTAMPTZ DEFAULT NOW()
```

#### postmaker.drafts — 生成结果

```sql
id            BIGSERIAL PRIMARY KEY
material_id   BIGINT REFERENCES postmaker.materials(id)
persona_id    TEXT NOT NULL
title         TEXT NOT NULL
body          TEXT NOT NULL
status        TEXT DEFAULT 'completed'
model_used    TEXT
output_path   TEXT
created_at    TIMESTAMPTZ DEFAULT NOW()
UNIQUE (material_id, persona_id)    -- 同一素材 + 人设不重复生成
```

---

## 组件交互

```
┌─────────────────────────────────────────────┐
│                DataRadar                     │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ RSS      │  │ Enricher │  │ AI        │ │
│  │ Fetcher  │→│ Extractor│→│ Summarizer│ │
│  └──────────┘  └──────────┘  └─────┬─────┘ │
│                                     │       │
│                              ┌──────▼──────┐│
│                              │ StorageManager│
│                              │ (asyncpg)    ││
│                              └──────┬──────┘│
│                                     │       │
│  ┌──────────┐  ┌──────────┐  ┌──────▼──────┐│
│  │ Redis    │←│ FastAPI  │←│ PostgreSQL  ││
│  │ Cache    │  │ Routers  │  │ Repository  ││
│  └──────────┘  └──────────┘  └─────────────┘│
│                     │                        │
└─────────────────────┼────────────────────────┘
                      │ REST API (:8000)
┌─────────────────────┼────────────────────────┐
│                PostMaker                      │
│                     │                        │
│  ┌──────────────────▼───────────────────┐   │
│  │         DataRadarClient              │   │
│  │    (httpx async HTTP client)         │   │
│  └──────────────────┬───────────────────┘   │
│                     │                        │
│  ┌──────────┐  ┌────▼─────┐  ┌───────────┐ │
│  │ Persona  │→│ Matcher  │→│ Content   │ │
│  │ Loader   │  │ Engine   │  │ Generator │ │
│  └──────────┘  └──────────┘  └─────┬─────┘ │
│                                     │       │
│                    ┌────────────────┼──────┐│
│                    │                │      ││
│              ┌─────▼─────┐  ┌──────▼─────┐││
│              │ Markdown  │  │ HTML       │││
│              │ Output    │  │ Output     │││
│              └───────────┘  └────────────┘││
│                                           ││
└───────────────────────────────────────────┘│
```

---

## 缓存策略

DataRadar API 使用 Redis 分级 TTL 缓存：

| 端点类型 | TTL | 说明 |
|----------|-----|------|
| 列表/搜索/热点 | 300s (5min) | 数据更新较频繁 |
| 详情页 | 1800s (30min) | 单条内容不常变 |
| 语义搜索 | 不缓存 | 查询参数复杂，缓存命中率低 |
| 标记使用 | 不缓存 | 写操作 |

缓存键格式：基于请求参数生成，ETL 后处理阶段会主动清除当日缓存。
