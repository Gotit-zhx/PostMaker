# PostMaker · DataRadar

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Storage](https://img.shields.io/badge/Storage-SQLite%20%7C%20PostgreSQL-336791)](https://www.postgresql.org/)
[![Status](https://img.shields.io/badge/Status-local--first%20MVP-orange)](docs/roadmap.md)

**PostMaker · DataRadar** 是一个面向个人创作者和小型内容团队的内容情报与生产工作台。它从 RSS 和网页中采集公开信息，整理为可搜索素材，再通过可配置的写作 persona 生成草稿，交由人工审核、编辑和导出。

项目把两项职责分开：**DataRadar 负责发现与整理素材，PostMaker 负责生成与审核内容**。你可以只使用 CLI，也可以运行本地审核工作台完成从数据源配置到 Markdown 导出的完整流程。

```text
RSS / 网页 → DataRadar 采集与整理 → 素材检索 → persona 匹配
                                             ↓
Markdown / HTML ← 导出 ← 人工审核 ← PostMaker 生成草稿
```

## 目录

- [功能](#功能)
- [快速开始](#快速开始)
- [CLI 示例](#cli-示例)
- [配置概览](#配置概览)
- [文档](#文档)
- [项目状态与限制](#项目状态与限制)
- [开发与测试](#开发与测试)
- [安全提示](#安全提示)

## 功能

- **采集与整理**：管理 RSS 源，可选配置 Playwright 网页目标；提取全文并可选生成摘要、分类、标签和重要性评分。
- **素材知识库**：通过 CLI、REST API 和工作台查看、搜索、筛选热门素材；默认使用 SQLite，可配置 PostgreSQL 和 Redis。
- **多人设生成**：用 YAML 定义写作 persona，根据主题兴趣和重要性匹配素材；支持模型生成和可选的二阶段润色。
- **人工审核闭环**：在浏览器中添加、测试和管理 RSS 源，启动采集，选择素材和 persona，编辑草稿、查看修订、批准、归档并导出 Markdown。
- **本地优先**：不配置模型也能采集和浏览素材；模型只在启用 AI 摘要或生成内容时调用。

## 快速开始

### 环境

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- RSS 采集和 SQLite 模式不要求 Docker；PostgreSQL、Redis、RSSHub 等服务可选。

### 安装依赖

在仓库根目录运行：

```bash
cd DataRadar
uv sync --all-extras

cd ../PostMaker
uv sync --all-extras
```

需要网页采集或浏览器回退全文提取时，再安装 Playwright Chromium：

```bash
cd DataRadar
uv run playwright install chromium
```

### 启动本地工作台

终端一：启动 DataRadar API。首次运行时可从示例文件创建本地配置；SQLite 是默认存储：

```bash
cd DataRadar
cp config/config.example.yaml config/config.yaml
DATARADAR_SQLITE_PATH=./output/dataradar.sqlite3 \
uv run uvicorn api_server.main:app --host 127.0.0.1 --port 8000
```

终端二：启动 PostMaker 工作台：

```bash
cd PostMaker
export DATARADAR_API_BASE="http://127.0.0.1:8000"
export AI_API_KEY="your-api-key"
export AI_MODEL="deepseek/deepseek-chat"
uv run postmaker workbench
```

打开 <http://127.0.0.1:8787>，进入“数据源”添加 RSS，测试并保存后点击“立即采集”；采集完成后到“素材发现”选择素材和 persona，生成草稿，经人工编辑、批准后导出 Markdown。采集与浏览不需要 AI 密钥；只有 AI 摘要或生成步骤需要模型配置。

首次使用的完整步骤、认证工作区配置和故障排查见[中文操作指南](docs/user-guide.md)。

## CLI 示例

```bash
# DataRadar：采集、检查和查询素材
cd DataRadar
uv run dataradar fetch
uv run dataradar status
uv run dataradar source list
uv run dataradar kb search "大模型" --limit 10
uv run dataradar kb trending --limit 10

# PostMaker：检查 persona、预览匹配并生成草稿
cd ../PostMaker
uv run postmaker personas
uv run postmaker generate --trending --limit 3 --dry-run
uv run postmaker generate --trending --limit 3
```

CLI 的完整选项和网页工作台每个页面的操作步骤见[操作指南](docs/user-guide.md)。

## 配置概览

| 文件或环境变量 | 用途 |
|---|---|
| `DataRadar/config/config.yaml` | RSS、网页目标、采集和 AI 摘要配置；可从 `config.example.yaml` 复制 |
| `PostMaker/config/config.yaml` | DataRadar 地址、模型和输出配置 |
| `PostMaker/config/personas/` | 写作 persona 定义 |
| `DATARADAR_SQLITE_PATH` | DataRadar 本地 SQLite 文件路径 |
| `DATARADAR_API_BASE` | PostMaker 访问 DataRadar API 的地址 |
| `AI_API_KEY`、`AI_MODEL`、`AI_API_BASE` | 模型凭据、模型名称及可选兼容 API 地址 |
| `POSTMAKER_AUTH_REQUIRED`、`DATARADAR_AUTH_REQUIRED` | 启用工作台登录及 DataRadar workspace 签名校验 |
| `WORKSPACE_AUTH_SECRET` | 两个服务共享的 workspace 签名密钥 |

模型名使用 LiteLLM 格式，例如 `deepseek/deepseek-chat`。密钥应通过环境变量或部署平台的密钥存储提供，不要写入版本控制中的配置文件。

## 文档

- [中文操作指南](docs/user-guide.md)：安装、数据源配置、采集、检索、CLI、工作台审核、备份和排障
- [系统架构](docs/architecture.md) · [REST API 参考](docs/api-reference.md)
- [部署指南](docs/deployment.md) · [persona 指南](docs/persona-guide.md) · [测试指南](docs/testing.md)
- [完整链路审计](docs/full-chain-audit-report.md) · [产品目标](docs/product-goal.md) · [路线图](docs/roadmap.md)

## 项目状态与限制

当前版本是可在本地运行的 **local-first MVP**。工作台支持匿名本地模式，也可以启用账号登录和按用户隔离的 SQLite 工作区。它不会自动向公众号、知乎、小红书等外部平台发布内容。

认证工作区模式适用于 SQLite 单机部署。PostgreSQL 仓储尚未加入 workspace 隔离，采集任务状态保存在 DataRadar 进程内，团队权限和共享任务队列也尚未实现。因此当前版本不是开箱即用的公网多租户 SaaS；公网部署前请阅读[部署指南](docs/deployment.md)和[完整链路审计](docs/full-chain-audit-report.md)。

## 开发与测试

```bash
cd DataRadar
uv run pytest tests/ -q

cd ../PostMaker
uv run pytest tests/ -q -m "not e2e"
```

E2E 测试需要运行中的 DataRadar API、模型配置及额外服务。开发分支和测试流程见[测试指南](docs/testing.md)。

## 安全提示

- 不要把 API key、数据库文件或生成产物提交到 Git。
- 对外部署时启用认证和 HTTPS，设置强随机 `WORKSPACE_AUTH_SECRET`，限制 DataRadar API 的可访问范围，并配置限流。
- RSS 和网页采集会访问外部地址；仅添加你有权访问和处理的公开来源。
