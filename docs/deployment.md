# 部署指南

## 开发环境

### 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Docker + Docker Compose（用于 PostgreSQL 和 Redis）

### 1. 启动基础设施

```bash
cd DataRadar/docker
cp .env.example .env     # 首次：编辑 .env 填入密码和 API Key
docker compose up postgres redis -d
```

可选启动 RSSHub 代理：

```bash
docker compose up postgres redis rsshub -d
```

### 2. 安装 DataRadar

```bash
cd DataRadar
uv sync --all-extras

# 可选：安装 Playwright 浏览器（用于网页采集和全文提取回退）
uv run playwright install chromium
```

### 3. 安装 PostMaker

```bash
cd PostMaker
uv sync --all-extras
```

### 4. 运行

```bash
# 终端 1：运行采集
cd DataRadar
uv run dataradar fetch

# 终端 2：启动 API
cd DataRadar
POSTGRES_DSN="postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base" \
REDIS_URL="redis://localhost:6379/0" \
uv run uvicorn api_server.main:app --port 8000

# 终端 3：生成内容
cd PostMaker
AI_API_KEY="your-key" AI_MODEL="openai/gpt-4o" \
uv run postmaker generate --trending --limit 5
```

### 一键安装（DataRadar）

```bash
# Mac/Linux
cd DataRadar
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Windows
cd DataRadar
scripts\setup.bat
```

脚本自动安装 uv、Python 3.12+、所有依赖、Playwright 浏览器，并启动 Docker 基础设施。

---

## Docker 全栈部署

### 服务架构

```
┌─────────────────────────────────────────────┐
│            docker-compose.yml               │
│                                             │
│  ┌──────────┐  ┌──────┐  ┌──────────────┐ │
│  │ postgres │  │ redis│  │   rsshub     │ │
│  │  :5432   │  │:6379 │  │   :1200      │ │
│  └────┬─────┘  └──┬───┘  └──────────────┘ │
│       │           │                        │
│  ┌────▼───────────▼────┐                   │
│  │    api-server       │                   │
│  │    (FastAPI)        │                   │
│  │    :8000 (内部)     │                   │
│  └────────┬────────────┘                   │
│           │                                │
│  ┌────────▼────────────┐                   │
│  │      nginx          │                   │
│  │    :8000 (外部)     │                   │
│  └─────────────────────┘                   │
└─────────────────────────────────────────────┘
```

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| postgres | pgvector/pgvector:pg16 | 5432 | PostgreSQL 16 + pgvector 扩展 |
| redis | redis:7-alpine | 6379 | 缓存，512MB LRU 策略 |
| rsshub | diygod/rsshub:latest | 1200 | RSSHub 代理（可选） |
| api-server | 自构建 | 8000（内部） | FastAPI 4 workers + uvloop |
| nginx | nginx:alpine | 8000（外部） | 反向代理 |

### 启动

```bash
cd DataRadar/docker
cp .env.example .env     # 编辑配置
docker compose up -d     # 启动全部 5 个服务
```

### 仅基础设施（本地开发）

```bash
docker compose up postgres redis -d
# 或
docker compose up postgres redis rsshub -d
```

---

## 环境变量

### DataRadar

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `AI_API_KEY` | 否 | — | LLM API 密钥（启用 AI 摘要时需要） |
| `AI_MODEL` | 否 | config.yaml 中的值 | LLM 模型（LiteLLM 格式，如 `openai/gpt-4o`） |
| `AI_API_BASE` | 否 | — | 自定义 API 端点 |
| `POSTGRES_DSN` | 否 | — | PostgreSQL 连接串；不设置时使用 SQLite |
| `REDIS_URL` | 否 | — | Redis 连接串（无则跳过缓存） |
| `EMBED_MODEL` | 否 | — | 嵌入模型（启用语义搜索） |
| `EMBED_API_KEY` | 否 | `OPENAI_API_KEY` | 嵌入 API 密钥 |
| `EMBED_API_BASE` | 否 | — | 嵌入 API 端点 |
| `ALLOWED_ORIGINS` | 否 | `*` | CORS 允许来源（逗号分隔） |
| `POSTGRES_PASSWORD` | 否 | `dataradar_secret` | Docker 中 PostgreSQL 密码 |
| `DATARADAR_AUTH_REQUIRED` | 否 | `false` | 拒绝缺少有效 workspace 签名的 API 请求 |
| `DATARADAR_WORKSPACES_DIR` | 否 | `output/workspaces` | SQLite 多用户数据根目录 |
| `WORKSPACE_AUTH_SECRET` | 多用户时必填 | — | 与 PostMaker 共享的 HMAC 密钥 |

### PostMaker

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `AI_API_KEY` | 生成时需要 | — | LLM API 密钥（仅生成内容时需要） |
| `AI_MODEL` | 否 | config.yaml 中的值 | LLM 模型 |
| `AI_API_BASE` | 否 | — | 自定义 API 端点 |
| `POSTGRES_DSN` | 否 | — | PostgreSQL 连接串（启用去重和历史） |
| `POSTMAKER_AUTH_REQUIRED` | 否 | `false` | 强制登录才能访问工作台 API |
| `POSTMAKER_AUTH_DB` | 否 | `PostMaker/output/auth.sqlite3` | 用户和 session 数据库 |
| `POSTMAKER_WORKSPACES_DIR` | 否 | `output/workspaces` | 工作台草稿数据库根目录 |
| `POSTMAKER_COOKIE_SECURE` | HTTPS 时必填 | `false` | 设置后浏览器仅通过 HTTPS 发送 session cookie |
| `WORKSPACE_AUTH_SECRET` | 多用户时必填 | — | 与 DataRadar 使用相同的强随机密钥 |

### 多用户 SQLite 部署

PostMaker 和 DataRadar 必须共享同一 `WORKSPACE_AUTH_SECRET`，并同时启用 `POSTMAKER_AUTH_REQUIRED=true`、`DATARADAR_AUTH_REQUIRED=true`。工作台的 session cookie 使用 `HttpOnly`、`SameSite=Lax` 和 CSRF token；HTTPS 部署还必须设置 `POSTMAKER_COOKIE_SECURE=true`。将 `POSTMAKER_AUTH_DB`、`POSTMAKER_WORKSPACES_DIR` 和 `DATARADAR_WORKSPACES_DIR` 指向持久化磁盘，并限制 DataRadar API 只允许 PostMaker 服务访问。

该隔离实现以 SQLite 独立文件为边界。PostgreSQL repositories 仍是单库模式。DataRadar 的采集状态保存在 API 进程内存，Docker Compose 和文档中的启动命令固定为单 worker；在迁移到共享任务队列和持久化状态前，不要直接增加 worker 或把多个 API 实例放到负载均衡后。

---

## 定时采集

### crontab（Linux/Mac）

```bash
# 每 4 小时运行一次采集
0 */4 * * * cd /path/to/DataRadar && uv run dataradar fetch >> /var/log/dataradar.log 2>&1
```

### systemd timer（Linux）

```ini
# /etc/systemd/system/dataradar-fetch.service
[Unit]
Description=DataRadar data collection

[Service]
Type=oneshot
WorkingDirectory=/path/to/DataRadar
ExecStart=/path/to/uv run dataradar fetch
Environment=AI_API_KEY=your-key
Environment=POSTGRES_DSN=postgresql://...
```

```ini
# /etc/systemd/system/dataradar-fetch.timer
[Unit]
Description=Run DataRadar collection every 4 hours

[Timer]
OnCalendar=*-*-* 00/4:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now dataradar-fetch.timer
```

### Windows 任务计划

```powershell
$action = New-ScheduledTaskAction -Execute "uv" `
    -Argument "run dataradar fetch" `
    -WorkingDirectory "C:\path\to\DataRadar"
$trigger = New-ScheduledTaskTrigger -Once -At "00:00" `
    -RepetitionInterval (New-TimeSpan -Hours 4) `
    -RepetitionDuration (New-TimeSpan -Days 365)
Register-ScheduledTask -TaskName "DataRadar Fetch" `
    -Action $action -Trigger $trigger
```

### DataRadar 内置调度

```bash
uv run dataradar schedule --interval 240    # 每 240 分钟
```

---

## 生产部署建议

### 数据库

- **备份**：使用 `pg_dump` 定期备份 `knowledge_base` 数据库
- **连接池**：默认 asyncpg 连接池大小适用于中小规模，高并发可调整 `min_size`/`max_size`
- **pgvector 索引**：当内容量超过 10 万条时，考虑调整 IVFFlat 的 `lists` 参数

### Redis

- Docker 配置默认 512MB + LRU 淘汰策略，适用于大多数场景
- 缓存数据全部可重建（从 PostgreSQL），Redis 不需要持久化

### API 服务

- 默认 4 个 uvicorn worker，可根据 CPU 核数调整
- Docker 中使用 uvloop 提升异步性能
- Nginx 反向代理提供额外的缓冲和连接管理

### 安全

- PostgreSQL 和 Redis 端口默认绑定 `127.0.0.1`，不暴露到公网
- 生产环境应设置 `ALLOWED_ORIGINS` 限制 CORS 来源
- API 密钥通过环境变量传入，不要硬编码在配置文件中
- Docker Compose 中的 `.env` 文件不应提交到版本控制
