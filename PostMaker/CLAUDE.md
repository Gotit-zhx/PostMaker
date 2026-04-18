# PostMaker 项目开发文档

## 项目概述

PostMaker 是矩阵运营内容生成系统，从 DataRadar REST API 获取素材，通过多人设匹配引擎和两阶段 LLM 内容生成，输出 Markdown + HTML 双格式的差异化原创内容。

**核心流程**：DataRadar API → 素材获取 → 人设匹配 → Prompt 构建 → LLM 生成 → 双格式输出

**设计原则**：Phase 1 仅做内容生成，不做平台发布；素材来源为 DataRadar HTTP API；PostgreSQL 存储可选。

---

## 目录结构

```
PostMaker/
├── postmaker/                       # 主包
│   ├── __init__.py
│   ├── __main__.py                  # CLI 入口（argparse）
│   ├── ai/
│   │   └── client.py                # AIClient（LiteLLM 封装）
│   ├── cli/
│   │   ├── generate.py              # generate 命令（主流程）
│   │   ├── personas.py              # personas 命令
│   │   ├── materials.py             # materials 命令
│   │   ├── history.py               # history 命令
│   │   └── config_cmd.py            # config 命令
│   ├── content/
│   │   ├── generator.py             # ContentGenerator（两阶段生成）
│   │   └── prompt_builder.py        # Prompt 模板加载与组装
│   ├── core/
│   │   ├── config.py                # 配置加载（YAML + 环境变量覆盖）
│   │   └── models.py                # Pydantic 数据模型
│   ├── integrations/
│   │   └── dataradar_client.py      # DataRadar REST API 客户端
│   ├── output/
│   │   ├── markdown.py              # Markdown 输出（含 YAML frontmatter）
│   │   └── html.py                  # HTML 输出（Markdown→HTML + 模板）
│   ├── persona/
│   │   ├── loader.py                # YAML frontmatter + Markdown body 解析
│   │   └── matcher.py               # 素材-人设匹配引擎
│   └── storage/
│       ├── db.py                    # asyncpg 连接池
│       ├── repository.py            # PostMakerRepository CRUD
│       └── schema.sql               # PostgreSQL DDL（postmaker schema）
│
├── config/
│   ├── config.yaml                  # 主配置
│   └── personas/                    # 人设定义
│       ├── tech-reviewer.yaml
│       └── code-craftsman.yaml
│
├── prompts/generate/
│   └── content_prompt.txt           # [system] + [user] 生成模板
│
├── templates/
│   └── article.html                 # HTML 输出模板
│
├── tests/                           # 测试（48 个）
│   ├── conftest.py                  # 共享 fixtures + mock 数据
│   ├── test_config.py               # 配置加载
│   ├── test_models.py               # 数据模型
│   ├── test_persona_loader.py       # 人设解析
│   ├── test_persona_matcher.py      # 人设匹配
│   ├── test_prompt_builder.py       # Prompt 构建
│   ├── test_output.py               # 双格式输出
│   ├── test_dataradar_client.py     # API 客户端（respx mock）
│   ├── test_generator.py            # 内容生成器
│   ├── test_pipeline_integration.py # 全管道集成测试
│   └── test_e2e.py                  # E2E（需真实环境）
│
└── pyproject.toml
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| LLM 接口 | LiteLLM（支持 100+ 供应商） |
| HTTP 客户端 | httpx（async） |
| 数据模型 | Pydantic v2 |
| Markdown 转换 | python-markdown |
| 配置 | PyYAML |
| JSON 修复 | json-repair |
| 重试 | tenacity |
| 数据库 | asyncpg（可选） |
| 测试 | pytest + pytest-asyncio + respx |

---

## CLI 命令

```bash
postmaker generate [--persona X] [--topic Y] [--material-id N] \
                   [--trending] [--limit N] [--dry-run] [--refine]
postmaker personas
postmaker materials [--search Q] [--trending] [--detail ID]
postmaker history [--persona X]
postmaker config [section]
```

---

## 核心模块说明

### 1. 配置系统（core/config.py）

加载 `config/config.yaml`，环境变量覆盖：
- `AI_API_KEY` → `ai.api_key`
- `AI_MODEL` → `ai.model`
- `AI_API_BASE` → `ai.api_base`
- `POSTGRES_DSN` → `database.postgres_dsn`

### 2. 数据模型（core/models.py）

| 模型 | 用途 |
|------|------|
| `Material` | 素材（id, title, source_platform, importance_score, tags, category, ai_summary, full_text） |
| `Persona` | 人设（id, name, style, system_prompt, interests） |
| `PersonaStyle` | 风格（tone, language, length_preference） |
| `PersonaInterests` | 兴趣（topics, min_importance） |
| `Draft` | 生成结果（material_id, persona_id, title, body, status, model_used） |
| `DraftStatus` | PENDING / COMPLETED / FAILED |
| `GenerationTask` | 生成任务（material + persona） |

### 3. 人设系统（persona/）

**loader.py**：解析 YAML frontmatter + Markdown body → `Persona` 对象

```
--- (YAML frontmatter)
id, name, style, interests
---
Markdown body → persona.system_prompt
```

**matcher.py**：

```python
match_material_to_personas(material, personas)
# importance >= min_importance AND (topics 交集非空 OR topics 为空匹配所有)

build_generation_tasks(materials, personas, existing_pairs)
# 素材 × 匹配人设 → 任务列表，跳过 existing_pairs 中已有的组合
```

### 4. DataRadar 客户端（integrations/dataradar_client.py）

异步 HTTP 客户端，调用 DataRadar REST API：

| 方法 | 端点 |
|------|------|
| `list_content(date, limit)` | GET /api/v1/content |
| `get_content_detail(id)` | GET /api/v1/content/{id} |
| `search(query, limit)` | GET /api/v1/content/search |
| `get_trending(date, limit)` | GET /api/v1/content/trending |
| `get_trending_topics(date)` | GET /api/v1/content/topics/trending |
| `get_bundle(category, limit)` | GET /api/v1/content/bundle |
| `mark_used(id, persona_id)` | POST /api/v1/content/{id}/mark_used |

### 5. 内容生成器（content/）

**prompt_builder.py**：加载 `prompts/generate/content_prompt.txt`，替换变量：
- system prompt 注入 persona.system_prompt
- user prompt 注入素材信息
- 优先使用 ai_summary，摘要不足 100 字时回退到 full_text[:3000]
- length_preference 映射：short=800-1200字, medium=1500-2500字, long=3000-5000字

**generator.py**：
- `generate_batch(tasks)` — asyncio.Semaphore(5) 并发生成
- `_generate_one(task)` — 单任务生成：build_messages → chat → parse_output
- 模型路由：importance ≥ 4 用 `models.high`，否则用 `models.medium` 或默认
- Refiner：可选二阶段编辑优化，最多 1 轮
- 输出解析：首行为标题（去 #），其余为 Markdown 正文

### 6. 输出模块（output/）

**markdown.py**：`output/{date}/{persona_id}/{slug}.md`
- YAML frontmatter: title, persona, source, generated_at, model
- Markdown body

**html.py**：`output/{date}/{persona_id}/{slug}.html`
- python-markdown 转 HTML（fenced_code, tables, codehilite）
- 嵌入 HTML 模板（内联 CSS，无外部依赖）
- 模板优先加载 `templates/article.html`

### 7. 存储层（storage/，可选）

仅在配置了 `database.postgres_dsn` 时启用。

```sql
postmaker.materials   — 素材本地副本（dataradar_id UNIQUE）
postmaker.drafts      — 生成结果（material_id + persona_id UNIQUE 去重）
```

---

## 生成管道流程

```
cmd_generate(args)
    │
    ├─ 1. 加载配置 + 人设
    │
    ├─ 2. DataRadarClient 获取素材
    │      ├─ --material-id → get_content_detail()
    │      ├─ --topic → get_bundle()
    │      ├─ --trending → get_trending()
    │      └─ 默认 → list_content()
    │
    ├─ 3. [可选] 加载已生成记录（去重）
    │
    ├─ 4. build_generation_tasks() → 匹配人设
    │
    ├─ 5. [dry-run?] 打印匹配结果并退出
    │
    ├─ 6. generate_batch(tasks) → 并发 LLM 生成
    │      ├─ build_messages(task)
    │      ├─ AIClient.chat() → 生成
    │      └─ [refine] → 二阶段优化
    │
    ├─ 7. 保存 .md + .html
    │
    └─ 8. [可选] 写入 PostgreSQL
```

---

## 运行方式

```bash
# 安装
uv sync --all-extras

# 生成内容（需 DataRadar API 运行中）
AI_API_KEY="..." AI_MODEL="openai/gpt-4o" \
uv run postmaker generate --trending --limit 5

# 运行测试
uv run pytest tests/ -v -m "not e2e"
```
