# PostMaker · DataRadar

一个面向个人创作者和小型内容团队的本地内容情报与生产系统。

它把公开信息采集、全文提取、素材检索、多人设写作、人工审核和 Markdown 导出串成一条可复用的工作流：

```text
RSS / 网页
   │
   ▼
DataRadar：采集 → 全文提取 → 可选 AI 摘要 → SQLite / PostgreSQL
   │
   ▼
REST API：列表、搜索、趋势、素材包
   │
   ▼
PostMaker：素材匹配 → persona 生成 → 人工编辑审核 → Markdown 导出
```

项目适合用来搭建个人科技资讯工作台、内容团队的素材库，或作为“采集系统 + LLM 内容生产 + 人工审核”产品原型。它当前定位为本地优先的生产工具，**不会自动向公众号、知乎、小红书等平台发布内容**。

## 目录

- [功能](#功能)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [常用命令](#常用命令)
- [配置和模型](#配置和模型)
- [文档](#文档)
- [技术栈](#技术栈)
- [当前边界](#当前边界)

## 功能

### DataRadar：素材采集和知识库

- 从 RSS 源采集文章、播客等内容，也可以配置 Playwright 网页采集目标。
- 按 Trafilatura、Playwright、Jina Reader 的顺序尝试提取全文。
- 可选调用 LiteLLM 支持的模型生成结构化摘要、分类、标签和重要性评分。
- 默认使用本地 SQLite；配置 `POSTGRES_DSN` 后可使用 PostgreSQL，配置 Redis 后启用缓存。
- 提供关键词搜索、可选语义搜索、热门内容、主题趋势、素材包和健康检查 API。
- 提供 `dataradar` CLI 管理数据源、运行采集、查询内容和查看状态。

### PostMaker：内容生成和审核

- 用 YAML frontmatter + Markdown body 定义多个 persona。
- 按素材分类、标签和重要性匹配适合的 persona。
- 支持 Composer 生成和可选 Refiner 二阶段优化；模型通过 LiteLLM 配置。
- 输出带 frontmatter 的 Markdown 和内联 CSS HTML。
- 支持素材与 persona 的去重记录；配置 PostgreSQL 后可查看生成历史。
- 提供本地审核工作台：发现素材、选择 persona、生成草稿、编辑、保存修订、批准、归档和导出 Markdown。

## 快速开始

### 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- 仅运行本地 SQLite 链路时不需要 Docker。
- 使用 PostgreSQL、Redis、RSSHub 或全栈部署时需要 Docker Compose。

### 1. 安装依赖

```bash
cd DataRadar
uv sync --all-extras

# 网页采集或全文提取需要时安装 Chromium
uv run playwright install chromium

cd ../PostMaker
uv sync --all-extras
```

### 2. 启动 DataRadar API（SQLite）

在第一个终端执行：

```bash
cd DataRadar
DATARADAR_SQLITE_PATH=./output/dataradar.sqlite3 \
uv run uvicorn api_server.main:app --host 127.0.0.1 --port 8000
```

如果不设置 `POSTGRES_DSN`，DataRadar 会使用 SQLite。第二个终端运行一次采集：

```bash
cd DataRadar
uv run dataradar fetch
```

检查 API：

```bash
curl http://127.0.0.1:8000/health
curl 'http://127.0.0.1:8000/api/v1/content?limit=5'
```

### 3. 配置模型并生成内容

在第二个终端设置模型供应商的密钥和模型名。示例：

```bash
cd PostMaker
export AI_API_KEY="your-api-key"
export AI_MODEL="deepseek/deepseek-chat"
export DATARADAR_API_BASE="http://127.0.0.1:8000"

uv run postmaker personas
uv run postmaker generate --trending --limit 3 --dry-run
uv run postmaker generate --trending --limit 3
```

生成文件默认位于 `PostMaker/output/{日期}/{persona-id}/`。

### 4. 启动本地审核工作台

```bash
cd PostMaker
uv run postmaker workbench
```

浏览器打开 <http://127.0.0.1:8787>。工作台保存草稿到 `output/workbench.sqlite3`；只有状态为“已批准”的草稿可以导出 Markdown。

### PostgreSQL / Redis 部署

需要持久化数据库、缓存或 RSSHub 时：

```bash
cd DataRadar/docker
cp .env.example .env
# 按需编辑 POSTGRES_PASSWORD、AI_API_KEY、EMBED_MODEL 等变量
docker compose up postgres redis -d
```

然后使用 PostgreSQL DSN 启动 API：

```bash
cd ..
POSTGRES_DSN="postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base" \
REDIS_URL="redis://localhost:6379/0" \
uv run uvicorn api_server.main:app --host 127.0.0.1 --port 8000
```

完整 Docker 部署、环境变量和定时采集见 [部署指南](docs/deployment.md)。

## 项目结构

```text
.
├── DataRadar/                 # 采集、存储、REST API 和 dataradar CLI
│   ├── dataradar/             # Python 包
│   ├── api_server/            # FastAPI 应用
│   ├── config/                # 采集源和模型配置
│   ├── docker/                # PostgreSQL、Redis、RSSHub、API 的 Compose 配置
│   └── tests/
├── PostMaker/                 # persona、生成器、输出器和审核工作台
│   ├── postmaker/             # Python 包和 CLI
│   ├── config/personas/       # persona 文件
│   ├── prompts/               # 生成提示词
│   ├── output/                # Markdown、HTML 和工作台数据库
│   └── tests/
├── docs/                      # 共享架构、部署、API 和操作文档
└── 运维手册.md                 # 中文运维补充说明
```

## 常用命令

### DataRadar

```bash
uv run dataradar fetch                         # 运行完整采集管道
uv run dataradar status                        # 查看系统状态
uv run dataradar rss --days 3 --limit 50       # 查询 RSS 内容
uv run dataradar rss --search "大模型"          # 搜索 RSS 内容
uv run dataradar source list                   # 列出数据源
uv run dataradar source test <id-or-url>       # 测试数据源
uv run dataradar kb search "关键词"             # 知识库全文搜索
uv run dataradar kb trending --limit 20        # 查看热门内容
uv run dataradar kb stats                      # 查看统计
uv run dataradar config ai                     # 查看脱敏后的 AI 配置
uv run dataradar schedule --interval 240       # 每 240 分钟运行一次采集
```

### PostMaker

```bash
uv run postmaker personas                      # 查看 persona
uv run postmaker materials --trending          # 查看热门素材
uv run postmaker materials --detail 42         # 查看素材详情
uv run postmaker generate --topic AI --limit 3  # 按主题生成
uv run postmaker generate --material-id 42 \
  --persona tech-reviewer                      # 指定素材和 persona
uv run postmaker history --persona tech-reviewer # 查看 PostgreSQL 历史
uv run postmaker workbench --port 9000         # 换端口启动审核工作台
```

## 配置和模型

- DataRadar 配置模板：[`DataRadar/config/config.example.yaml`](DataRadar/config/config.example.yaml)
- PostMaker 配置：[`PostMaker/config/config.yaml`](PostMaker/config/config.yaml)
- persona 示例：[`PostMaker/config/personas/`](PostMaker/config/personas/)
- 常用环境变量：`AI_API_KEY`、`AI_MODEL`、`AI_API_BASE`、`DATARADAR_API_BASE`、`DATARADAR_TIMEOUT`、`POSTGRES_DSN`、`REDIS_URL`、`DATARADAR_SQLITE_PATH`、`POSTMAKER_WORKBENCH_DB`

模型调用不是运行本地采集和 API 的必要条件。关闭 AI 摘要后，DataRadar 仍可采集和存储素材；PostMaker 生成和工作台生成草稿则需要配置 `AI_API_KEY` 与 `AI_MODEL`。建议先用低成本模型完成筛选和初稿，仅在需要时开启 `--refine`。

## 文档

- [中文操作指南](docs/user-guide.md)：从安装、配置到采集、生成、审核和导出
- [系统架构](docs/architecture.md)：组件、数据流和存储设计
- [REST API 参考](docs/api-reference.md)：DataRadar 接口和请求示例
- [部署指南](docs/deployment.md)：Docker、环境变量和定时任务
- [persona 指南](docs/persona-guide.md)：创建和调试写作 persona
- [测试指南](docs/testing.md)：测试分层、命令和 Mock 策略
- [完整链路审计](docs/full-chain-audit-report.md)：当前闭环验证结果、限制和后续优先级
- [产品目标](docs/product-goal.md) · [路线图](docs/roadmap.md)

## 技术栈

| 层 | 技术 |
|---|---|
| 语言与包管理 | Python 3.12+、uv |
| 采集 | feedparser、httpx、Trafilatura、Playwright、Jina Reader |
| 存储 | SQLite（默认）、PostgreSQL 16、pgvector、pg_trgm |
| 缓存 | Redis 7 |
| API | FastAPI、uvicorn |
| 模型接入 | LiteLLM |
| 内容输出 | Markdown、HTML |

## 当前边界

- 工作台是单用户本地审核工具，当前没有登录、团队权限和并发编辑冲突处理。
- 自动发布适配器尚未实现，批准后的内容需要人工复制或由后续渠道适配器处理。
- 语义搜索需要额外配置 embedding 模型和 API key。
- SQLite 适合本地开发和小规模单机使用；多进程或高并发场景应切换 PostgreSQL。

## 测试

```bash
cd DataRadar && uv run pytest tests/ -v
cd ../PostMaker && uv run pytest tests/ -v -m "not e2e"
```

需要真实模型和运行中的 DataRadar API 时，再执行 PostMaker 的 E2E 测试。详见 [测试指南](docs/testing.md)。
