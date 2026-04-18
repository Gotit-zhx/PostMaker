# DataRadar 项目分析报告

## 一、项目概述

DataRadar 是一个 **数据采集与知识库系统**，核心目标是从多种互联网信息源（RSS 订阅、网页爬虫、RSSHub）自动化采集内容，经过全文提取、AI 摘要、向量嵌入等处理后，存入结构化知识库，并通过 REST API 提供高性能的语义搜索与全文检索能力。

**一句话定位**：面向信息密集型用户的自动化内容聚合与智能检索平台。

---

## 二、核心功能

### 2.1 多源数据采集

| 采集方式 | 实现 | 说明 |
|---------|------|------|
| RSS 订阅 | feedparser | 20+ 预配置源（HN、TechCrunch、Wired、MIT Tech Review 等），支持自定义添加 |
| RSSHub 代理 | RSSHub Docker | Reddit、YouTube、Product Hunt、少数派、财联社等需要 API 转换的源 |
| Playwright 网页爬虫 | playwright + stealth | CSS 选择器驱动，支持 JS 渲染页面（Product Hunt、GitHub Trending） |

- 采集阶段**全量入库不过滤**，过滤逻辑下沉到检索/查询时
- 每个 RSS 源可独立配置 `max_age_days` 控制新鲜度
- 支持 HTTP 代理，适配网络受限环境

### 2.2 三引擎全文提取

通过三级引擎串行回退策略提取文章全文：

```
优先级 1: Trafilatura（本地库，零延迟，覆盖约 80% 静态页面）
    ↓ 失败
优先级 2: Playwright（JS 渲染回退，共享浏览器实例，3 并发）
    ↓ 失败
优先级 3: Jina Reader API（云端兜底，带频率限制）
```

批量模式采用三阶段并行架构：
- 阶段 1：所有 URL 并发 Trafilatura（20 并发线程）
- 阶段 2：失败 URL 用共享 Playwright 浏览器回退
- 阶段 3：剩余失败用并发 Jina API 兜底（5 并发）

### 2.3 AI 智能摘要

- 基于 LiteLLM 统一接口，支持 100+ AI 提供商（OpenAI、DeepSeek、Anthropic、Gemini、Ollama 等）
- 为每篇文章生成约 200 token 的 RAG 检索摘要
- 10 并发线程池并行调用 LLM API
- 可配置提示词模板（`config/etl/summarize_prompt.txt`）

### 2.4 ETL 管道（SQLite → PostgreSQL）

采集数据先落地到 SQLite，再通过异步 ETL 管道写入 PostgreSQL 知识库：

```
Transform（SQLite 提取） → Embed（向量嵌入） → Load（PostgreSQL upsert）
    → Aggregate（标题相似度聚合） → Invalidate Cache（Redis 缓存清除）
```

- 标题相似度聚合：基于 Jaccard 系数（阈值 0.5），将多平台报道同一事件的内容合并为 `knowledge_entries`
- 向量嵌入：LiteLLM 调用 `text-embedding-3-small`（1536 维），批量生成
- 去重机制：`(source_platform, source_url)` 唯一约束 + content_hash

### 2.5 知识库检索

PostgreSQL 16 + pgvector + pg_trgm 提供两种搜索模式：

| 搜索类型 | 技术实现 | 适用场景 |
|---------|---------|---------|
| 全文搜索 | pg_trgm GIN 索引 | 精确关键词匹配，支持中英文 |
| 语义搜索 | pgvector IVFFlat 索引 | 模糊语义匹配，概念相关度搜索 |

### 2.6 REST API

FastAPI 构建的高性能 REST 服务：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/content` | GET | 内容列表（分页、日期/类型/平台过滤） |
| `/api/v1/content/search?q=` | GET | 全文搜索（pg_trgm） |
| `/api/v1/content/semantic` | POST | 语义搜索（pgvector） |
| `/api/v1/knowledge` | GET | 知识条目列表 |
| `/api/v1/knowledge/{id}` | GET | 条目详情（含关联来源） |
| `/api/v1/stats` | GET | 统计概览 + 热门内容 |
| `/health` | GET | 健康检查 |

### 2.7 CLI 命令行

```bash
dataradar fetch                          # 运行完整采集管道
dataradar status                         # 系统状态
dataradar rss [--days N] [--search Q]    # 查询 RSS 数据
dataradar source list/add/remove/test    # 源管理
dataradar kb search/semantic/list/stats  # 知识库查询
dataradar read <URL>                     # 读取文章全文
dataradar config [section]               # 查看配置
```

---

## 三、技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.12+ | 全栈开发语言 |
| Web 框架 | FastAPI + Uvicorn | REST API 服务 |
| 异步运行时 | asyncio + asyncpg | 高并发 I/O |
| 关系数据库 | PostgreSQL 16 + pgvector + pg_trgm | 知识库存储与检索 |
| 本地存储 | SQLite | 原始采集数据暂存 |
| 缓存 | Redis 7 | API 响应缓存 |
| LLM 接口 | LiteLLM | 统一多供应商 AI 调用 |
| RSS 解析 | feedparser | RSS/Atom 源解析 |
| 全文提取 | Trafilatura + Playwright + Jina | 三引擎文章提取 |
| 网页爬虫 | Playwright + playwright-stealth | JS 渲染页面采集 |
| 配置管理 | PyYAML + ruamel.yaml | 读取/保留注释写入配置 |
| 数据验证 | Pydantic 2.0 | API 请求/响应验证 |
| 重试机制 | tenacity | 指数退避重试 |
| 容器化 | Docker + Docker Compose + Nginx | 生产环境部署 |

---

## 四、架构设计

### 4.1 整体数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据采集层                                │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐         │
│  │ RSS 源    │  │ RSSHub 代理   │  │ Playwright 爬虫    │         │
│  │ (15+ 源)  │  │ (Reddit 等)   │  │ (PH, GitHub)      │         │
│  └─────┬─────┘  └──────┬───────┘  └────────┬──────────┘         │
│        └───────────────┼───────────────────┘                    │
│                        ▼                                        │
│               ┌─────────────────┐                               │
│               │ RSSData 统一模型  │                               │
│               └────────┬────────┘                               │
└────────────────────────┼────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        内容增强层                                │
│  ┌──────────────────────────────────────────────┐               │
│  │ 三引擎全文提取                                  │               │
│  │ Trafilatura → Playwright → Jina Reader        │               │
│  └──────────────────────┬───────────────────────┘               │
│                         ▼                                       │
│  ┌──────────────────────────────────────────────┐               │
│  │ AI 摘要生成（LiteLLM，10 并发）                  │               │
│  └──────────────────────┬───────────────────────┘               │
└─────────────────────────┼───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        存储层                                    │
│  ┌────────────────────┐     ┌─────────────────────────────┐     │
│  │ SQLite（本地暂存）    │────→│ ETL 管道                      │     │
│  │ output/rss/{日期}.db │     │ Transform→Embed→Load→Aggregate│     │
│  └────────────────────┘     └────────────┬────────────────┘     │
│                                          ▼                      │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ PostgreSQL + pgvector（知识库）                        │       │
│  │ content_items ← knowledge_content_map → knowledge_entries │  │
│  └──────────────────────────────────────────────────────┘       │
│  ┌────────────────┐                                             │
│  │ Redis（缓存层）   │                                             │
│  └────────────────┘                                             │
└─────────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        服务层                                    │
│  ┌───────────────────────────┐  ┌─────────────────┐            │
│  │ FastAPI REST API           │  │ CLI 命令行        │            │
│  │ (content/knowledge/stats) │  │ (fetch/rss/kb)   │            │
│  └───────────────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 模块职责

```
dataradar/                    # 主包
├── collector.py              # 采集管道编排器（6 阶段流水线）
├── context.py                # 应用上下文（统一配置访问接口）
├── source_manager.py         # RSS/Web 源的 CRUD（ruamel.yaml 保留注释写入）
├── cli/                      # CLI 子命令（argparse 多子命令架构）
├── ai/                       # AI 模块
│   ├── client.py             # LiteLLM 封装（统一调用接口）
│   ├── summarizer.py         # 批量摘要生成器（ThreadPoolExecutor）
│   ├── filter.py             # AI 内容过滤/标签（可选）
│   └── prompt_loader.py      # 提示词模板加载器
├── crawler/                  # 数据采集
│   ├── rss/                  # RSS 抓取 + 解析
│   └── web/                  # Playwright 网页爬虫
├── enricher/                 # 内容增强
│   └── extractor.py          # 三引擎全文提取器
├── storage/                  # SQLite 存储层（Mixin 架构）
│   ├── base.py               # 数据模型（RSSItem, RSSData, NewsItem）
│   ├── local.py              # LocalStorage 实现
│   ├── sqlite_*_mixin.py     # 按功能分离的 Mixin（RSS/News/AI）
│   └── schema.sql            # SQLite DDL
├── services/                 # 数据访问服务层
└── utils/                    # 工具函数（时间、URL、日期解析、校验器）

knowledge_base/               # PostgreSQL 知识库层
├── db.py                     # asyncpg 连接池管理
├── cache.py                  # Redis 缓存管理（分级 TTL）
├── repository.py             # CRUD 仓储（ContentRepository, KnowledgeRepository）
├── schema.sql                # PostgreSQL DDL（pgvector + pg_trgm）
└── etl/                      # ETL 管道
    ├── pipeline.py           # 管道编排（5 阶段）
    ├── transformer.py        # SQLite → ContentItemInput 转换
    └── embedder.py           # LiteLLM 批量向量嵌入

api_server/                   # FastAPI REST 服务
├── main.py                   # 应用入口 + lifespan 资源管理
├── schemas.py                # Pydantic 响应模型
├── routers/                  # 路由处理器（content, knowledge, stats）
└── middleware/cache.py       # HTTP 响应缓存中间件
```

### 4.3 数据库设计

**SQLite（本地暂存）**

每天一个独立数据库文件（`output/rss/{YYYY-MM-DD}.db`），表结构包括：
- `platforms` — 平台信息
- `news_items` — 热榜新闻（含排名追踪）
- `rank_history` — 排名变化历史
- `title_changes` — 标题变更记录
- `crawl_records` / `crawl_source_status` — 抓取记录与状态

**PostgreSQL（知识库）**

三张核心表 + 一张追踪表：
- `content_items` — 统一多模态内容存储（text/video/audio/image），含 pgvector 向量字段
- `knowledge_entries` — 跨平台去重聚合后的知识条目
- `knowledge_content_map` — M:N 关联表
- `etl_sync_records` — ETL 同步追踪

索引策略：
- 时间分区索引（最频繁查询条件）
- 复合索引（类型+日期、平台+日期）
- GIN 索引（标签数组、标题/全文三元组）
- IVFFlat 向量索引（余弦相似度，lists=100）

### 4.4 部署架构

```
Docker Compose 服务栈：
┌──────────┐   ┌──────────┐   ┌──────────┐
│ PostgreSQL│   │  Redis   │   │  RSSHub  │
│  pgvector │   │  7-alpine│   │  (可选)   │
│  :5432    │   │  :6379   │   │  :1200   │
└─────┬─────┘   └─────┬────┘   └──────────┘
      │               │
      ▼               ▼
┌─────────────────────────────┐
│  API Server (Uvicorn×4)     │
│  FastAPI + uvloop           │
│  :8000 (内部)                │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  Nginx (反向代理)            │
│  :8000 (对外) → :3333 (内部) │
└─────────────────────────────┘
```

---

## 五、设计理念

### 5.1 采集与过滤分离

**核心原则**：采集阶段全量入库不过滤，过滤功能下沉到检索/查询时。

这一设计避免了因过滤逻辑变更导致历史数据丢失的问题，保证了数据的完整性。用户可以在查询时动态调整过滤条件，而不需要重新采集。

### 5.2 渐进式引擎回退

全文提取采用三级引擎串行回退策略，在成本、速度与覆盖率之间取得平衡：
- Trafilatura：本地运行，零成本，处理大部分静态页面
- Playwright：JS 渲染能力，处理动态页面
- Jina Reader：云端兜底，覆盖剩余长尾场景

### 5.3 两级存储架构

SQLite + PostgreSQL 的两级存储设计：
- SQLite 作为采集阶段的轻量级本地暂存，零部署依赖
- PostgreSQL 作为知识库的持久化存储，提供企业级查询能力
- ETL 管道异步桥接两者，不阻塞采集流水线

### 5.4 LLM 供应商无关

通过 LiteLLM 抽象层实现 AI 供应商无关：
- 支持 100+ AI 提供商的统一接口
- 配置中只需修改 `model` 和 `api_key` 即可切换供应商
- 支持自定义 API 端点（`api_base`），兼容任意 OpenAI 协议的服务

### 5.5 可选依赖分层

通过 `pyproject.toml` 的 optional-dependencies 实现依赖分层：
- 基础包：仅 RSS 采集 + SQLite 存储（最小依赖）
- `[full]`：添加 Trafilatura + Playwright（全文提取）
- `[kb]`：添加 asyncpg + Redis（知识库）
- `[api]`：添加 FastAPI + Uvicorn（REST 服务）
- `[all]`：全量安装

---

## 六、存在的不足

### 6.1 架构层面

1. **配置管理硬编码**：`config.yaml` 中包含了 API Key 明文（`ai.api_key`），存在安全风险。虽然支持环境变量替换，但默认配置文件中直接写入了真实密钥。

2. **同步/异步混用**：采集管道中 RSS 抓取（`fetcher.fetch_all()`）是同步调用，摘要生成使用 `ThreadPoolExecutor`，而 ETL 管道和全文提取是异步。这种混合模式增加了代码复杂度，且同步部分无法充分利用 I/O 并发。

3. **聚合算法过于简单**：知识条目的聚合使用基于空格分词的 Jaccard 系数（阈值 0.5），对中文内容效果差（中文不按空格分词），且 0.5 的阈值可能导致不相关的内容被误聚合。

4. **缺少任务调度**：没有内置的定时调度器（如 APScheduler 或 Celery Beat），需要依赖外部 cron 或手动触发采集。

### 6.2 数据层面

5. **SQLite 按日分库**：每天一个独立 SQLite 文件（`output/rss/{日期}.db`），跨天查询需要遍历多个数据库文件，性能和实现复杂度较高。

6. **向量嵌入默认关闭**：`embedding.enabled` 默认为 `false`，语义搜索这一核心能力在默认配置下不可用，降低了开箱即用体验。

7. **缺少增量同步机制**：ETL 管道按整天批量处理，没有基于 change log 或 WAL 的增量同步，对于频繁更新的场景效率较低。

### 6.3 代码质量

8. **错误处理粗粒度**：多处使用 `except Exception` 全捕获，吞掉了具体异常信息，不利于问题诊断。ETL 的 `_aggregate` 方法中异常被 `logger.debug` 静默记录。

9. **缺少单元测试**：项目中没有测试目录或测试文件，关键逻辑（聚合算法、全文提取回退、ETL 管道）缺乏测试覆盖。

10. **日志与 print 混用**：采集管道中大量使用 `print()` 输出状态信息，而部分模块使用 `logging`，缺乏统一的日志策略。

### 6.4 运维层面

11. **缺少监控与告警**：没有 Prometheus 指标暴露、健康检查细化（当前 `/health` 只返回 `{"status": "ok"}`，不检查数据库/Redis 连接状态）。

12. **Docker 网络安全**：PostgreSQL 和 Redis 端口绑定到 `127.0.0.1`，但 Nginx 端口绑定到 `0.0.0.0`，在无防火墙的服务器上存在暴露风险。

13. **缺少数据备份策略**：SQLite 文件和 PostgreSQL 数据缺少自动化备份机制。

---

## 七、优化方案

### 7.1 短期优化（低成本、高收益）

#### P0：安全加固
- 从 `config.yaml` 移除明文 API Key，统一使用环境变量或 `.env` 文件
- 将 `config.yaml` 加入 `.gitignore`，提供 `config.example.yaml` 模板
- 细化 `/health` 端点，检查 PostgreSQL/Redis 连接状态

#### P1：中文聚合优化
- 将 `_title_similar()` 中的空格分词替换为字符级 n-gram 或引入 jieba 分词
- 对中英文内容采用不同的相似度策略

#### P2：统一日志
- 将所有 `print()` 替换为 `logging`，通过 `logging.config` 统一管理
- 按模块配置日志级别，生产环境关闭 debug 日志

#### P3：添加测试
- 为核心模块添加单元测试（聚合算法、URL 处理、日期解析）
- 为 ETL 管道添加集成测试（使用 testcontainers 或 SQLite mock）

### 7.2 中期优化（提升能力）

#### 内置任务调度
- 集成 APScheduler 或 asyncio 原生调度，支持配置化的定时采集
- 支持 cron 表达式配置采集频率

#### 增量 ETL
- 基于 SQLite 的 `last_crawl_time` 字段实现增量同步
- 引入 ETL 水位线机制，避免重复处理

#### 全异步改造
- 将 RSS 抓取改为 `aiohttp`/`httpx` 异步实现
- 将 AI 摘要生成从 `ThreadPoolExecutor` 改为 `asyncio` 原生并发
- 统一采集管道为全异步架构

#### 向量嵌入优化
- 默认启用 embedding（或提供更清晰的引导）
- 支持本地嵌入模型（如通过 Ollama 运行 nomic-embed-text）
- 实现增量 embedding（仅对新增/更新内容生成向量）

### 7.3 长期优化（架构演进）

#### 可观测性
- 集成 Prometheus 指标（采集速率、成功率、延迟分布）
- 添加 Grafana 仪表盘模板
- 结构化日志（JSON 格式）+ ELK/Loki 接入

#### 前端界面
- 开发 Web 管理界面（源管理、采集监控、内容浏览）
- 知识库搜索的可视化界面
- 采集状态 Dashboard

#### 内容分析增强
- 实体抽取（NER）：自动识别文章中的公司、人物、产品
- 趋势分析：基于时间序列的热度变化追踪
- 跨源关联：基于向量相似度的自动知识图谱构建

#### 分布式扩展
- 采集任务队列化（Celery/RQ），支持多 Worker 并行采集
- PostgreSQL 读写分离 + 表分区（按月分区）
- Redis Cluster 支持高可用缓存

---

## 八、总结

DataRadar 是一个设计思路清晰、功能完整的数据采集与知识库系统。项目在以下方面表现突出：

- **架构设计合理**：采集-增强-存储-检索的分层流水线，职责清晰
- **技术选型务实**：LiteLLM 实现 LLM 无关、三引擎回退保证全文提取覆盖率、PostgreSQL+pgvector 提供企业级检索能力
- **可扩展性好**：可选依赖分层、配置化源管理、Docker 一键部署
- **开发体验友好**：Claude Skills 集成、完善的 CLI 工具

主要改进方向集中在：安全加固（API Key 管理）、中文处理优化（分词/聚合）、运维能力提升（监控/调度/测试）、以及全异步改造以提升并发性能。这些优化可以分阶段推进，优先处理安全性和数据质量相关的问题。
