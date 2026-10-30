# DataRadar

**数据采集与知识库系统** — 从 RSS 源和网页采集内容，经全文提取和可选的 AI 结构化摘要后写入 PostgreSQL 或本地 SQLite，提供 REST API 和语义搜索。

## 核心流程

```
RSS 源（15+）─────────────────┐
  直接 RSS + RSSHub 代理      │
                              ├─→ 全文提取 → AI 结构化摘要（可选） → PostgreSQL / SQLite
Playwright 网页采集（可选）────┘                                     │
                                                              后处理（可选）
                                                          embedding + 聚合
                                                                    │
                                                              Redis 缓存
                                                                    │
                                                            FastAPI REST API
```

**采集管道 5 阶段**：

1. RSS 全量采集（不过滤）
2. Playwright 网页采集（可选）
3. 三引擎全文提取：Trafilatura → Playwright → Jina Reader
4. AI 结构化摘要（JSON：summary + category + tags + importance）
5. PostgreSQL 直写（asyncpg UPSERT）
6. 后处理（可选）：embedding 生成 + 知识聚合

---

## 快速开始

### 安装

```bash
# 安装 uv（如已安装可跳过）
# Mac/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 同步依赖
uv sync --all-extras

# 安装 Playwright 浏览器（可选，用于网页采集和 JS 渲染回退）
uv run playwright install chromium
```

### 一键安装

```bash
# Mac/Linux
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Windows
scripts\setup.bat
```

### Docker 基础设施

```bash
cd docker
cp .env.example .env            # 首次：编辑 .env
docker compose up postgres redis -d   # 启动 PostgreSQL + Redis
```

没有 PostgreSQL 时可直接使用 SQLite 完成本地开发和联调：

```bash
DATARADAR_SQLITE_PATH=/tmp/dataradar.sqlite3 \
uv run uvicorn api_server.main:app --host 127.0.0.1 --port 8000
```

SQLite 是无 `POSTGRES_DSN` 时的默认后端；采集器、REST API 和 `dataradar rss` 查询命令共用同一个文件。生产环境仍建议使用 PostgreSQL、Redis 和 pgvector。

### 运行采集

```bash
uv run dataradar fetch          # 运行完整采集管道
uv run dataradar status         # 查看状态
```

### 启动 API 服务

```bash
# Mac/Linux:
POSTGRES_DSN="postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base" \
REDIS_URL="redis://localhost:6379/0" \
uv run uvicorn api_server.main:app --host 0.0.0.0 --port 8000 --workers 1

# Windows:
set POSTGRES_DSN=postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base
set REDIS_URL=redis://localhost:6379/0
uv run uvicorn api_server.main:app --host 0.0.0.0 --port 8000 --workers 1
```

数据源采集状态目前保存在 API 进程内存中，因此默认使用单 worker，保证工作台查询到的任务状态与实际采集任务一致。扩展到多 worker 前，需要先把采集任务和状态迁移到共享队列及持久化存储。

---

## CLI 命令

```bash
# ── 数据采集 ──
dataradar fetch                              # 运行完整采集管道
dataradar status                             # 系统状态

# ── RSS 数据查询 ──
dataradar rss [--feeds X] [--days N]         # 查询 RSS 数据
dataradar rss --search "keyword"             # 搜索 RSS
dataradar rss --status                       # RSS 源数据统计

# ── 源管理 ──
dataradar source list                        # 列出所有源
dataradar source add rss <url> [--id X]      # 添加 RSS 源
dataradar source add web <url> [--id X]      # 添加 Web 采集目标
dataradar source remove <id>                 # 删除源
dataradar source enable/disable <id>         # 启用/禁用源
dataradar source test <id|url>               # 测试源

# ── 知识库 ──
dataradar kb search <query>                  # 全文搜索
dataradar kb semantic <query>                # 语义搜索
dataradar kb list [--date D] [--type T]      # 内容列表
dataradar kb trending [--date D]             # 热门内容
dataradar kb stats                           # 统计信息

# ── 文章阅读 ──
dataradar read <url>                         # 读取文章全文

# ── 配置 ──
dataradar config [section]                   # 查看配置
```

---

## AI 结构化摘要

采集管道中的 AI 摘要阶段输出 JSON 格式：

```json
{
  "summary": "200字以内摘要",
  "category": "AI",
  "tags": ["GPT", "OpenAI", "LLM"],
  "importance": 4
}
```

**分类**：AI / 云计算 / 开源 / 网络安全 / 商业 / 硬件 / 开发工具 / 其他

**重要性**：1=日常 2=参考价值 3=值得关注 4=重要事件 5=行业里程碑

Token 优化：智能截断（首段+末段+中间抽样，上限 1500 字符）、规则预判跳过低价值内容。

---

## REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/content` | GET | 内容列表（游标分页） |
| `/api/v1/content/{id}` | GET | 内容详情 |
| `/api/v1/content/search?q=` | GET | 关键词搜索 |
| `/api/v1/content/semantic` | POST | 语义搜索 |
| `/api/v1/content/trending` | GET | 热点排行 |
| `/api/v1/content/topics/trending` | GET | 分类趋势 |
| `/api/v1/content/bundle?category=` | GET | 素材包 |
| `/api/v1/content/{id}/mark_used` | POST | 标记已使用 |
| `/api/v1/knowledge` | GET | 知识条目 |
| `/api/v1/knowledge/semantic` | POST | 知识条目语义搜索 |
| `/api/v1/stats/overview` | GET | 统计 |
| `/health` | GET | 健康检查 |

完整 API 文档：[docs/api-reference.md](../docs/api-reference.md)

---

## Docker 全栈部署

```bash
cd docker
docker compose up -d    # 启动全部 5 个服务
```

| 服务 | 说明 | 端口 |
|------|------|------|
| postgres | PostgreSQL 16 + pgvector | 5432 |
| redis | Redis 7 缓存 | 6379 |
| rsshub | RSSHub 代理（可选） | 1200 |
| api-server | FastAPI 服务 | 8000（内部） |
| nginx | 反向代理 | 8000 |

---

## 配置

主配置文件：`config/config.yaml`

关键配置段：

```yaml
rss:
  enabled: true
  feeds:
    - id: "hacker-news"
      name: "Hacker News"
      url: "https://hnrss.org/frontpage"
      enabled: true

knowledge_base:
  postgres_dsn: ""          # 或环境变量 POSTGRES_DSN
  enricher:
    enabled: true           # 全文提取
  summarizer:
    enabled: true           # AI 摘要

ai:
  model: ""                 # 环境变量 AI_MODEL
  api_key: ""               # 环境变量 AI_API_KEY

webhook:
  enabled: false
  url: ""                   # 采集完成通知 URL
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| 数据库 | PostgreSQL 16 + pgvector + pg_trgm |
| 异步驱动 | asyncpg |
| 缓存 | Redis 7（分级 TTL） |
| LLM 接口 | LiteLLM（100+ 供应商） |
| Web 框架 | FastAPI + uvicorn |
| HTTP 客户端 | httpx（async） |
| RSS 解析 | feedparser |
| 全文提取 | Trafilatura + Playwright + Jina Reader |
| 配置 | PyYAML / ruamel.yaml |
