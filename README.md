# PostMaker 矩阵运营系统

**DataRadar 数据采集 + PostMaker 内容生成** — 从 RSS 源采集素材，经 AI 分析后存入 PostgreSQL，再通过多人设生成差异化原创内容。

```
RSS 源（15+）──┐
               ├─→ DataRadar ─→ 全文提取 ─→ AI 摘要/分类 ─→ PostgreSQL
网页采集（可选）─┘                                                │
                                                           REST API
                                                                │
                                                           PostMaker
                                                         ┌──────┴──────┐
                                                    科技评论家      代码匠人
                                                    深度长文        实操分享
                                                         │           │
                                                      .md + .html  .md + .html
```

## 项目结构

| 目录 | 说明 |
|------|------|
| [DataRadar/](DataRadar/) | 数据采集与知识库系统 — RSS 采集、全文提取、AI 结构化摘要、PostgreSQL 存储、REST API |
| [PostMaker/](PostMaker/) | 内容生成系统 — 多人设匹配、两阶段 LLM 生成、Markdown + HTML 双格式输出 |
| [docs/](docs/) | 共享文档 — 系统架构、人设指南、部署手册、API 参考、测试指南 |

## 快速开始

### 1. 启动基础设施

```bash
cd DataRadar/docker
cp .env.example .env     # 编辑 .env 填入 AI_API_KEY 等
docker compose up postgres redis -d
```

### 2. DataRadar 采集数据

```bash
cd DataRadar
uv sync --all-extras
uv run dataradar fetch   # 运行完整采集管道
```

### 3. 启动 DataRadar API

```bash
POSTGRES_DSN="postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base" \
REDIS_URL="redis://localhost:6379/0" \
uv run uvicorn api_server.main:app --port 8000
```

### 4. PostMaker 生成内容

```bash
cd PostMaker
uv sync --all-extras
AI_API_KEY="your-key" AI_MODEL="openai/gpt-4o" \
uv run postmaker generate --trending --limit 5
```

生成的文件在 `PostMaker/output/{日期}/{人设ID}/` 下，每篇有 `.md` 和 `.html` 两种格式。

## 文档导航

- [系统架构](docs/architecture.md) — 全局数据流、组件关系、数据库设计
- [人设创建指南](docs/persona-guide.md) — YAML 格式、匹配规则、示例
- [部署指南](docs/deployment.md) — Docker 部署、环境变量、定时采集
- [API 参考](docs/api-reference.md) — DataRadar REST API 完整文档
- [测试指南](docs/testing.md) — 测试分层、运行方式、Mock 策略
- [矩阵运营设计](docs/matrix_operations_design.md) — 产品设计思考

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| 数据库 | PostgreSQL 16 + pgvector + pg_trgm |
| 缓存 | Redis 7 |
| LLM | LiteLLM（支持 100+ 模型供应商） |
| Web 框架 | FastAPI + uvicorn |
| HTTP 客户端 | httpx（async） |
| 全文提取 | Trafilatura + Playwright + Jina Reader |
| 包管理 | uv |
