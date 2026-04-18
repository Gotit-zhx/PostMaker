# DataRadar 项目开发文档

## 项目概述

DataRadar 是**数据采集 + 知识库系统**，从 RSS 源和可选的 Playwright 网页采集内容，经三引擎全文提取和 AI 结构化摘要后**直写 PostgreSQL**，通过可选的后处理管道生成 embedding 和知识聚合，提供 REST API 和语义搜索。

**核心流程**：RSS 采集 → 全文提取（Trafilatura → Playwright → Jina） → AI 结构化摘要 → PostgreSQL 直写 → 后处理（embedding + 聚合）→ REST API

**设计原则**：采集阶段全量入库不过滤，过滤功能下沉到检索/查询时。

---

## 目录结构

```
DataRadar/
├── dataradar/                       # 主包
│   ├── __init__.py                  # __version__ = "1.0.0"
│   ├── __main__.py                  # CLI 入口（argparse 多子命令）
│   ├── collector.py                 # DataCollector 采集管道（5 阶段 + 后处理）
│   ├── context.py                   # AppContext 统一配置接口
│   ├── source_manager.py            # 源管理器（ruamel.yaml 保留注释读写）
│   ├── ai/
│   │   ├── client.py                # AIClient（LiteLLM 封装）
│   │   ├── filter.py                # AI 智能过滤（可选）
│   │   ├── filter_pipeline.py       # AIFilterPipeline
│   │   ├── prompt_loader.py         # 提示词模板加载器
│   │   └── summarizer.py            # ContentSummarizer（JSON 结构化输出）
│   ├── cli/
│   │   ├── collect.py               # fetch, status, schedule
│   │   ├── rss.py                   # rss 查询/搜索
│   │   ├── source.py                # 源管理（add/remove/enable/disable/test）
│   │   ├── kb.py                    # 知识库查询
│   │   └── read.py                  # 文章阅读
│   ├── core/
│   │   ├── analyzer.py              # 内容分析
│   │   ├── data.py                  # 数据处理
│   │   ├── frequency.py             # 词频分析
│   │   ├── loader.py                # 配置加载
│   │   └── scheduler.py             # 定时调度
│   ├── crawler/
│   │   ├── rss/
│   │   │   ├── fetcher.py           # RSSFetcher（feedparser）
│   │   │   └── parser.py            # RSS 解析
│   │   └── web/
│   │       └── scraper.py           # PlaywrightScraper（网页采集）
│   ├── enricher/
│   │   └── extractor.py             # ArticleExtractor（三引擎全文提取）
│   ├── services/
│   │   ├── api_client.py            # KB HTTP 客户端
│   │   ├── cache_service.py         # LRU 缓存
│   │   ├── data_service.py          # RSS 数据查询
│   │   └── parser_service.py        # RSS 解析服务
│   ├── storage/
│   │   ├── base.py                  # RSSItem, RSSData 数据类
│   │   └── manager.py               # StorageManager（asyncpg 直写 PostgreSQL）
│   ├── tools/
│   │   ├── knowledge.py             # KB 搜索工具
│   │   └── article_reader.py        # Jina Reader 文章阅读
│   └── utils/
│       ├── date_parser.py           # 自然语言日期解析
│       ├── errors.py                # 自定义异常
│       ├── time.py                  # 时区工具
│       ├── url.py                   # URL 工具
│       └── validators.py            # 参数验证
│
├── knowledge_base/                  # PostgreSQL 知识库层
│   ├── db.py                        # asyncpg 连接池
│   ├── cache.py                     # Redis 分级 TTL 缓存
│   ├── schema.sql                   # DDL（pgvector + pg_trgm）
│   ├── repository.py                # ContentRepository + KnowledgeRepository
│   └── etl/
│       ├── pipeline.py              # ETLPipeline（后处理：embedding + 聚合）
│       └── embedder.py              # BatchEmbedder（LLM 向量生成）
│
├── api_server/                      # FastAPI REST 服务
│   ├── main.py                      # App + lifespan + 路由注册
│   ├── schemas.py                   # Pydantic 响应模型
│   ├── middleware/
│   │   └── cache.py                 # 响应缓存装饰器
│   └── routers/
│       ├── content.py               # 内容接口（8 个端点）
│       ├── knowledge.py             # 知识条目接口
│       └── stats.py                 # 统计接口
│
├── config/
│   ├── config.yaml                  # 主配置
│   ├── config.example.yaml          # 配置模板
│   ├── frequency_words.txt          # 关注词
│   ├── ai_interests.txt             # AI 过滤兴趣词
│   ├── etl/
│   │   └── summarize_prompt.txt     # AI 摘要提示词模板
│   ├── web_scraper/
│   │   └── extract_list_prompt.txt  # 网页采集提示词
│   └── ai_filter/
│       ├── prompt.txt               # AI 过滤系统提示词
│       ├── extract_prompt.txt       # 标签提取提示词
│       └── update_tags_prompt.txt   # 标签更新提示词
│
├── docker/
│   ├── docker-compose.yml           # 全栈（postgres/redis/rsshub/api/nginx）
│   ├── Dockerfile.api               # FastAPI 镜像
│   ├── manage.py                    # Docker 管理脚本
│   └── nginx.conf                   # 反向代理
│
├── tests/
│   ├── conftest.py
│   ├── test_config_loader.py
│   ├── test_date_parser.py
│   ├── test_title_similarity.py
│   └── test_url_utils.py
│
└── pyproject.toml
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| 异步 | async/await, asyncio |
| 数据库 | PostgreSQL 16 + pgvector + pg_trgm |
| 异步驱动 | asyncpg（直写，非 ORM） |
| 缓存 | Redis 7（分级 TTL） |
| LLM 接口 | LiteLLM（支持 100+ 供应商） |
| 向量嵌入 | text-embedding-3-small (1536-dim) |
| Web 框架 | FastAPI + uvicorn |
| HTTP 客户端 | httpx (async) / requests (sync) |
| RSS 解析 | feedparser |
| 全文提取 | Trafilatura + Playwright + Jina Reader |
| 网页采集 | Playwright + playwright-stealth（可选） |
| JSON 修复 | json-repair（处理 LLM 输出） |
| 重试 | tenacity |
| 配置 | PyYAML（只读）/ ruamel.yaml（读写，保留注释） |

---

## CLI 命令

```bash
# ── 数据采集 ──
dataradar fetch                              # 运行完整采集管道
dataradar status                             # 系统状态
dataradar schedule [--interval N]            # 定时采集

# ── RSS 数据查询 ──
dataradar rss [--feeds X] [--days N]         # 查询 RSS 数据
dataradar rss --search "keyword"             # 搜索 RSS
dataradar rss --status                       # RSS 源数据统计

# ── 源管理 ──
dataradar source list                        # 列出所有源
dataradar source add rss <url> [--id X] [--name Y]
dataradar source add web <url> [--id X] [--name Y] \
    [--list-selector S] [--title-selector S] [--link-selector S]
dataradar source remove <id>
dataradar source enable <id>
dataradar source disable <id>
dataradar source test <id|url>

# ── 知识库 ──
dataradar kb search <query> [--type T] [--limit N]
dataradar kb semantic <query> [--type T] [--date-from D] [--limit N]
dataradar kb list [--date D] [--type T] [--platform P] [--limit N] [--cursor C]
dataradar kb trending [--date D] [--type T] [--limit N]
dataradar kb stats
dataradar kb get <id>
dataradar kb entry <id>
dataradar kb related <id> [--limit N]

# ── 文章阅读 ──
dataradar read <url>
dataradar read --batch <url1> <url2>

# ── 配置 ──
dataradar config [section]
```

---

## 核心模块说明

### 1. 采集管道（collector.py — DataCollector）

5 个采集阶段 + 1 个后处理阶段：

```
① _fetch_rss()            → RSSFetcher（feedparser 解析所有 RSS 源）
② _fetch_web_pages()      → PlaywrightScraper（可选，JS 渲染网页采集）
③ _enrich_full_text()     → ArticleExtractor（三引擎全文提取）
④ _generate_summaries()   → ContentSummarizer（AI 结构化摘要）
⑤ save_rss_data()         → StorageManager（asyncpg UPSERT 直写）
⑥ _run_post_processing()  → ETLPipeline（embedding 生成 + 知识聚合）
```

采集完成后可触发 Webhook 通知（`_notify_webhook()`）。

### 2. 存储管理器（storage/manager.py — StorageManager）

**asyncpg 直写 PostgreSQL**，通过 `ON CONFLICT` 实现 UPSERT 去重：

```python
class StorageManager:
    async def init()                              # 初始化 asyncpg 连接池
    async def close()                             # 关闭连接
    async def save_rss_data(rss_data)             # 批量 UPSERT 到 content_items
    async def _upsert_item(item, conn)            # 单条 UPSERT
    async def detect_new_rss_items(rss_data)      # 检测新条目
    async def get_content_by_date(date, ...)      # 按日期查询
    async def search_content(keyword, ...)        # 关键词搜索
    async def get_feeds_status()                  # RSS 源统计
```

UPSERT 策略：
- 去重键：`(source_platform, source_url)`
- 冲突时：递增 `crawl_count`，COALESCE 保留非空的 `full_text`/`ai_summary`，GREATEST 取最高 `importance_score`

### 3. AI 结构化摘要（ai/summarizer.py — ContentSummarizer）

输出 JSON 格式（通过 `json-repair` 容错解析）：

```json
{
  "summary": "200字以内摘要",
  "category": "AI",
  "tags": ["GPT", "OpenAI", "LLM"],
  "importance": 4
}
```

**分类**（8 类）：AI / 云计算 / 开源 / 网络安全 / 商业 / 硬件 / 开发工具 / 其他

**重要性**（1-5）：1=日常 2=参考价值 3=值得关注 4=重要事件 5=行业里程碑

关键优化：
- **智能截断**（`_prepare_content`）：首段 + 末段 + 中间抽样，上限 1500 字符
- **规则预判**（`_should_skip`）：标题 < 10 字 或 摘要 > 200 字且无全文 → 跳过 LLM，复用 RSS 摘要
- **并发控制**：`asyncio.Semaphore(10)` 限制并发 LLM 请求

解析结果写入 RSSItem 字段：
- `item.ai_summary` ← summary
- `item.category` ← category（验证合法分类）
- `item.tags` ← tags（最多 10 个）
- `item.importance_score` ← importance（钳位 1.0-5.0）

### 4. 三引擎全文提取（enricher/extractor.py — ArticleExtractor）

按优先级逐层回退：

| 引擎 | 并发数 | 说明 |
|------|--------|------|
| Trafilatura | 20 线程 | 本地快速提取，最小 200 字符 |
| Playwright | 3 页面 | JS 渲染回退，可用 stealth 插件 |
| Jina Reader | 5 请求 | 云端兜底，需 API Key 解除限速 |

返回 `ExtractResult(url, text, images, method, word_count)`。

### 5. 知识库（knowledge_base/）

#### 数据库 Schema（schema.sql）

```sql
-- 核心表
content_items          — 采集内容（直写入库）
knowledge_entries      — 跨平台知识聚合条目
knowledge_content_map  — 知识条目 ↔ 内容关联
etl_sync_records       — ETL 进度追踪
content_usage_marks    — PostMaker 人设使用标记

-- 扩展
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector 向量搜索
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- 三元组文本搜索
```

`content_items` 核心字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL | 主键 |
| title | TEXT | 标题 |
| source_platform | TEXT | 来源（rss-{feed_id}） |
| source_url | TEXT | 原文 URL（UNIQUE 去重键） |
| date_partition | DATE | 日期分区 |
| summary | TEXT | RSS 原始摘要 |
| full_text | TEXT | 全文提取结果 |
| ai_summary | TEXT | AI 生成摘要 |
| importance_score | FLOAT | AI 重要性评分 |
| tags | TEXT[] | AI 提取标签 |
| category | TEXT | AI 分类 |
| embedding | vector(1536) | 语义搜索向量 |
| content_hash | TEXT | MD5(platform:url) |

#### Repository（repository.py）

**ContentRepository**（content_items 表）：

```python
async def upsert(item)                     # INSERT/UPDATE
async def upsert_batch(items)              # 批量写入
async def get_by_id(content_id)            # 详情
async def list_by_date(date_str, ...)      # 日期列表
async def search_fulltext(query, ...)      # pg_trgm 搜索
async def search_semantic(embedding, ...)  # 向量余弦相似度
async def get_trending(date_str, ...)      # 热点排行（importance DESC）
async def get_trending_topics(date_str, ...)  # 分类趋势
async def list_by_category(date_str, category, ...)  # 按分类筛选
async def mark_used(content_id, persona_id)  # 标记人设使用
async def list_without_embedding(date_str, limit)  # 待 embedding 列表
async def update_embedding(content_id, embedding)  # 更新向量
async def get_stats()                      # 全局统计
```

**KnowledgeRepository**（knowledge_entries 表）：

```python
async def upsert(entry)                    # 知识条目写入
async def get_by_id(entry_id)              # 详情（含来源列表）
async def list_recent(days, category, ...) # 近期条目
async def search_semantic(embedding, ...)  # 语义搜索
async def link_content(knowledge_id, content_id)  # 关联内容
```

#### ETL 后处理（etl/pipeline.py — ETLPipeline）

采集直写后的异步后处理：

```
① _embed_missing(date_str)     → 为缺少向量的内容生成 embedding
② _aggregate(date_str)         → 跨平台标题去重 → 聚合到 knowledge_entries
③ _invalidate_cache(date_str)  → 清除 Redis 缓存
```

标题去重算法：中文用 `SequenceMatcher`，英文用 Jaccard 词集相似度，阈值 0.6。

### 6. FastAPI REST 服务（api_server/）

#### 端点列表

| 端点 | 方法 | 缓存 | 说明 |
|------|------|------|------|
| `/api/v1/content` | GET | 300s | 内容列表（游标分页） |
| `/api/v1/content/{id}` | GET | 1800s | 内容详情 |
| `/api/v1/content/search?q=` | GET | 300s | 关键词搜索（pg_trgm） |
| `/api/v1/content/semantic` | POST | — | 语义搜索（需 EMBED_MODEL） |
| `/api/v1/content/trending` | GET | 300s | 热点排行 |
| `/api/v1/content/topics/trending` | GET | 300s | 分类趋势 |
| `/api/v1/content/bundle?category=` | GET | 300s | 素材包 |
| `/api/v1/content/{id}/mark_used` | POST | — | 标记人设使用 |
| `/api/v1/knowledge` | GET | — | 知识条目列表 |
| `/api/v1/knowledge/semantic` | POST | — | 知识语义搜索 |
| `/api/v1/stats/overview` | GET | — | 统计概览 |
| `/health` | GET | — | 健康检查 |

#### 响应模型（schemas.py）

```python
ContentItemSummary    # 列表项：id, title, source_platform, importance_score, tags, category
ContentItemDetail     # 详情：继承 Summary + full_text, image_urls, raw_metadata
ContentListResponse   # items + PageMeta（游标分页）
ContentSearchResponse # items + query + total
TrendingTopic         # category, count, sources, avg_importance, top_tags
ContentBundleResponse # category + items + total
MarkUsedRequest       # persona_id
```

### 7. 应用上下文（context.py — AppContext）

统一配置和工具访问接口：

```python
class AppContext:
    # 配置属性
    timezone, rss_config, rss_feeds, rss_enabled, ...

    # 时间操作
    get_time(), format_date(), format_time()

    # 存储操作
    get_storage_manager() → StorageManager

    # 数据处理
    read_today_titles(), detect_new_titles(), is_first_crawl()

    # 词频分析
    load_frequency_words(), matches_word_groups(), count_frequency()

    # AI 过滤
    run_ai_filter(), convert_ai_filter_to_report_data()
```

### 8. 源管理器（source_manager.py — SourceManager）

使用 `ruamel.yaml` 实现保留注释的 config.yaml 读写：

```python
mgr = SourceManager()
mgr.list_feeds()                           # 列出 RSS 源
mgr.add_feed(url="https://...", name="X")  # 添加源
mgr.test_feed("hacker-news")              # 测试源
mgr.remove_feed("custom-feed")            # 删除源
mgr.enable_feed("feed-id")                # 启用源
mgr.disable_feed("feed-id")               # 禁用源
```

---

## 数据模型

### RSSItem（storage/base.py）

```python
@dataclass
class RSSItem:
    title: str
    feed_id: str
    feed_name: str = ""
    url: str = ""
    published_at: str = ""        # ISO 格式
    summary: str = ""             # RSS 原始摘要
    author: str = ""
    full_text: str = ""           # 全文提取结果
    ai_summary: str = ""          # AI 生成摘要
    tags: List[str]               # AI 提取标签
    category: str = ""            # AI 分类
    importance_score: float = 0.0 # AI 评分（1-5）
    count: int = 1                # 抓取次数
```

### ContentItemInput（repository.py）

```python
@dataclass
class ContentItemInput:
    content_type: str             # text, video, audio, image
    title: str
    source_platform: str
    source_url: str
    date_partition: str           # YYYY-MM-DD
    summary: Optional[str]
    full_text: Optional[str]
    importance_score: float = 0.0
    tags: List[str]
    category: Optional[str]
    embedding: Optional[List[float]]
```

---

## 数据流图

```
RSS 源（15+）─────────────────┐
  直接 RSS + RSSHub 代理      │
                              ├─→ 全文提取 → AI 结构化摘要 → PostgreSQL 直写
Playwright 网页采集（可选）────┘                                     │
                                                              后处理（可选）
                                                          embedding + 聚合
                                                                    │
                                                              Redis 缓存
                                                                    │
                                                            FastAPI REST API
                                                                    │
                                                            PostMaker 消费
```

---

## 配置说明（config/config.yaml）

```yaml
app:
  timezone: "Asia/Shanghai"

rss:
  enabled: true
  feeds:
    - id: "hacker-news"
      name: "Hacker News"
      url: "https://hnrss.org/frontpage"
      max_age_days: 1
      enabled: true

ai:
  model: ""                    # 环境变量 AI_MODEL（LiteLLM 格式）
  api_key: ""                  # 环境变量 AI_API_KEY
  api_base: ""                 # 可选，自定义 API 端点
  timeout: 120
  temperature: 1.0
  max_tokens: 5000

knowledge_base:
  enabled: true
  postgres_dsn: ""             # 环境变量 POSTGRES_DSN
  redis_url: ""                # 环境变量 REDIS_URL
  enricher:
    enabled: true              # 全文提取
    use_playwright: true
    jina_api_key: ""
    rate_limit_per_min: 10
  summarizer:
    enabled: true              # AI 摘要
    max_tokens: 250
    batch_size: 20
    skip_if_exists: true
  embedding:
    enabled: false             # 向量生成（后处理）
    model: "openai/text-embedding-3-small"
    dimensions: 1536

web_scraper:
  enabled: true
  targets:
    - id: "producthunt"
      url: "https://www.producthunt.com"
      list_selector: "[data-test='post-item']"

webhook:
  enabled: false
  url: ""                      # 采集完成通知
```

---

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `AI_API_KEY` | LLM API 密钥 | `sk-...` |
| `AI_MODEL` | LLM 模型（LiteLLM 格式） | `openai/gpt-4o` |
| `POSTGRES_DSN` | PostgreSQL 连接串 | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `EMBED_MODEL` | 嵌入模型 | `openai/text-embedding-3-small` |
| `EMBED_API_KEY` | 嵌入 API 密钥 | `sk-...` |
| `EMBED_API_BASE` | 嵌入 API 端点（可选） | `https://...` |
| `ALLOWED_ORIGINS` | CORS 来源（默认 `*`） | `https://app.example.com` |

---

## 运行方式

```bash
# 安装
uv sync --all-extras
uv run playwright install chromium    # 可选

# 采集数据
uv run dataradar fetch

# 启动 API
POSTGRES_DSN="postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base" \
REDIS_URL="redis://localhost:6379/0" \
uv run uvicorn api_server.main:app --host 0.0.0.0 --port 8000 --workers 4

# Docker 全栈
cd docker && docker compose up -d
```
