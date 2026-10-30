# PostMaker · DataRadar

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Storage](https://img.shields.io/badge/Storage-SQLite%20%7C%20PostgreSQL-336791)](https://www.postgresql.org/)
[![Status](https://img.shields.io/badge/Status-local--first%20MVP-orange)](docs/roadmap.md)

> 从公开信息中发现值得写的内容，把素材变成可审核、可追溯、可导出的文章草稿。

PostMaker · DataRadar 是一个面向个人创作者和小型内容团队的本地内容情报与生产系统。它把数据采集、全文整理、素材检索、多人设写作、人工审核和 Markdown 导出串成一条工作流，适合搭建个人科技资讯工作台，也适合作为内容自动化产品的技术原型。

如果你第一次接触项目，建议先阅读 [中文操作指南](docs/user-guide.md)，再按本文的“5 分钟启动本地闭环”运行。README 负责说明项目是什么、能做什么以及如何启动；操作指南覆盖配置、日常使用、故障排查和备份。

项目采用 **DataRadar 负责找素材，PostMaker 负责写内容** 的分层设计：采集和生成可以单独运行，也可以通过本地 API 和审核工作台组成完整闭环。

```text
RSS / 网页
   │
   ▼
DataRadar：采集 → 全文提取 → 可选 AI 摘要 → SQLite / PostgreSQL
   │
   ▼
REST API：列表、搜索、趋势、素材详情
   │
   ▼
PostMaker：persona 匹配 → LLM 生成 → 人工编辑审核 → Markdown / HTML
```

## 为什么使用它

- **先看素材，再生成内容**：用热门、最新、搜索和主题维度筛选选题，减少盲目调用模型。
- **同一素材支持多种表达**：通过 persona 定义不同的读者、语气、篇幅和分析框架。
- **人工审核留在闭环里**：生成只是初稿，工作台支持编辑、批准、归档、修订恢复和导出。
- **本地优先，数据可控**：默认使用 SQLite，配置 PostgreSQL 和 Redis 后可以扩展到更大规模。
- **模型供应商可替换**：通过 LiteLLM 接入 OpenAI、DeepSeek、兼容 OpenAI 协议的服务或本地模型。

## 项目状态

项目当前是 **local-first MVP**：核心采集、检索、生成、人工审核和导出链路已经可以在单机上运行，适合个人使用、功能评估和二次开发。数据源页面支持在浏览器中完成 RSS 的测试、保存、启停和立即采集。

生产化部署仍需要补齐登录认证、租户权限、共享任务队列、并发编辑冲突处理和外部发布渠道适配。请把当前版本当作可运行的技术底座，不要直接暴露到公网作为无认证 SaaS。

## 功能

### DataRadar：内容采集与知识库

- 从 RSS 源采集文章、播客等内容，也支持配置 Playwright 网页采集目标。
- 按 Trafilatura、Playwright、Jina Reader 的顺序尝试提取全文。
- 可选调用模型生成摘要、分类、标签和重要性评分。
- 默认使用本地 SQLite；配置 `POSTGRES_DSN` 后可以使用 PostgreSQL，配置 `REDIS_URL` 后启用缓存。
- 提供内容列表、关键词搜索、热门内容、主题趋势、素材包、详情和健康检查 API。
- 提供 `dataradar` CLI 管理数据源、运行采集、查询素材和查看状态。

### PostMaker：内容生成与审核

- 使用 YAML frontmatter + Markdown body 定义多个 persona。
- 根据素材分类、标签和重要性匹配适合的 persona。
- 支持 Composer 生成和可选 Refiner 二阶段优化。
- 输出带 frontmatter 的 Markdown 和内联 CSS HTML。
- 支持素材与 persona 组合去重，以及 PostgreSQL 生成历史。
- 提供本地审核工作台：发现素材、选择 persona、生成草稿、编辑、保存修订、批准、归档和导出 Markdown。

## 5 分钟启动本地闭环

### 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- 仅使用 SQLite 时不需要 Docker。
- 使用 PostgreSQL、Redis、RSSHub 或完整 Docker 部署时需要 Docker Compose。

### 1. 安装依赖

```bash
cd DataRadar
uv sync --all-extras

# 只有网页采集或需要浏览器回退提取时才需要
uv run playwright install chromium

cd ../PostMaker
uv sync --all-extras
```

### 2. 准备 DataRadar

第一次使用时复制配置模板：

```bash
cd ../DataRadar
cp config/config.example.yaml config/config.yaml
```

先启动 API（默认 SQLite）：

```bash
DATARADAR_SQLITE_PATH=./output/dataradar.sqlite3 \
uv run uvicorn api_server.main:app --host 127.0.0.1 --port 8000
```

保持这个终端运行，再打开另一个终端执行一次采集：

```bash
cd DataRadar
uv run dataradar fetch
```

检查服务和素材：

```bash
curl http://127.0.0.1:8000/health
curl 'http://127.0.0.1:8000/api/v1/content?limit=5'
```

### 3. 配置模型并生成初稿

模型密钥建议只通过环境变量提供，不要写进 Git 跟踪的配置文件：

```bash
cd PostMaker
export AI_API_KEY="your-api-key"
export AI_MODEL="deepseek/deepseek-chat"
export DATARADAR_API_BASE="http://127.0.0.1:8000"

# 先查看人设并预览匹配，不消耗模型额度
uv run postmaker personas
uv run postmaker generate --trending --limit 3 --dry-run

# 确认后生成
uv run postmaker generate --trending --limit 3
```

生成文件默认写入 `PostMaker/output/{日期}/{persona-id}/`。

### 4. 打开审核工作台

```bash
cd PostMaker
uv run postmaker workbench
```

浏览器打开 <http://127.0.0.1:8787>，然后按以下顺序操作：

1. 在“素材库”选择热门或最新素材。
2. 查看摘要、标签、重要性和原文链接。
3. 选择 persona，点击“生成审核草稿”。
4. 修改标题和正文，保存后查看修订历史。
5. 确认事实和来源后批准草稿，或将其归档。
6. 在已批准草稿中导出 Markdown。

工作台草稿默认保存在 `PostMaker/output/workbench.sqlite3`。它当前是单用户本地工作台，不会自动发布到公众号、知乎、小红书等外部平台。

## 常用命令

以下命令需要在对应子项目目录中执行。

### DataRadar

```bash
cd DataRadar
uv run dataradar fetch                         # 运行完整采集管道
uv run dataradar status                        # 查看采集和存储状态
uv run dataradar source list                   # 列出 RSS / Web 数据源
uv run dataradar source test <id-or-url>       # 测试单个数据源
uv run dataradar rss --days 3 --limit 50       # 查询 RSS 内容
uv run dataradar rss --search "大模型"          # 搜索 RSS 内容
uv run dataradar kb search "关键词"             # 知识库全文搜索
uv run dataradar kb trending --limit 20        # 查看热门内容
uv run dataradar kb stats                      # 查看统计
uv run dataradar config ai                     # 查看脱敏后的 AI 配置
uv run dataradar schedule --interval 240       # 每 240 分钟运行一次采集
```

### PostMaker

```bash
cd PostMaker
uv run postmaker personas                       # 查看 persona
uv run postmaker materials --trending           # 查看热门素材
uv run postmaker materials --detail 42          # 查看素材详情
uv run postmaker generate --topic AI --limit 3  # 按主题生成
uv run postmaker generate --material-id 42 \
  --persona tech-reviewer                       # 指定素材和 persona
uv run postmaker history --persona tech-reviewer # 查看生成历史
uv run postmaker workbench --port 9000          # 使用其他端口启动工作台
```

## 配置与模型

| 配置 | 作用 | 常见设置 |
|---|---|---|
| `DataRadar/config/config.yaml` | RSS、网页目标、存储和采集参数 | 从 `config.example.yaml` 复制 |
| `PostMaker/config/config.yaml` | DataRadar 地址、模型和输出参数 | 可用环境变量覆盖 |
| `PostMaker/config/personas/` | 写作 persona | 每个 YAML 文件一个 persona |
| `DATARADAR_SQLITE_PATH` | DataRadar SQLite 路径 | 本地开发建议显式设置 |
| `POSTMAKER_WORKBENCH_DB` | 工作台草稿数据库路径 | 默认 `PostMaker/output/workbench.sqlite3` |
| `AI_API_KEY` / `AI_MODEL` | 模型密钥和模型名 | 生成内容时必填 |
| `AI_API_BASE` | OpenAI 兼容服务地址 | 使用代理或第三方服务时设置 |
| `DATARADAR_API_BASE` | PostMaker 访问 DataRadar 的地址 | 默认 `http://localhost:8000` |
| `POSTGRES_DSN` / `REDIS_URL` | PostgreSQL 和 Redis 连接 | 扩展部署时设置 |

模型调用不是运行采集 API 的必要条件。可以先关闭 AI 摘要，验证采集、存储和搜索，再用低成本模型完成筛选和初稿；`--refine` 会增加一次模型调用，建议只对少量重要稿件使用。

## 安全与部署边界

- 通过网页或 API 添加的 RSS 地址会校验协议、端口、域名解析结果和重定向目标，localhost、内网地址、保留地址和带凭据的 URL 会被拒绝。
- 当前工作台和数据源配置默认是单用户本地模式；DataRadar 的采集任务状态保存在当前进程内。
- API 默认没有登录认证。需要对外提供服务时，应先接入身份认证、权限控制、HTTPS、限流、审计日志和安全的密钥管理。
- 不要把 API key 写入 Git 跟踪的 YAML、README、日志或导出的文章；优先使用环境变量或部署平台的密钥存储。

## 项目结构

```text
.
├── DataRadar/                         # 采集、存储、REST API 和 dataradar CLI
│   ├── dataradar/                     # 采集器、解析器、存储和 CLI
│   ├── api_server/                    # FastAPI API
│   ├── config/                        # 数据源、AI 和采集配置
│   ├── docker/                        # PostgreSQL、Redis、RSSHub、API Compose 配置
│   └── tests/
├── PostMaker/                         # persona、生成器、输出器和审核工作台
│   ├── postmaker/                     # Python 包和 CLI
│   ├── config/personas/               # persona 文件
│   ├── prompts/                       # 生成提示词
│   ├── output/                        # Markdown、HTML 和工作台数据库
│   └── tests/
├── docs/                              # 架构、部署、API、测试和操作文档
├── scripts/                           # 启动、采集、生成、备份和健康检查脚本
└── 运维手册.md                         # 面向日常运维的中文补充说明
```

## 文档

- [中文操作指南](docs/user-guide.md)：从安装、配置、采集到生成、审核、导出和排障
- [系统架构](docs/architecture.md)：组件、数据流和存储设计
- [REST API 参考](docs/api-reference.md)：DataRadar API 路径、字段和请求示例
- [部署指南](docs/deployment.md)：Docker、环境变量、定时采集和生产部署
- [persona 指南](docs/persona-guide.md)：创建、匹配和调试写作 persona
- [测试指南](docs/testing.md)：测试分层、命令和 Mock 策略
- [完整链路审计](docs/full-chain-audit-report.md)：当前闭环验证结果和已知限制
- [产品目标](docs/product-goal.md) · [路线图](docs/roadmap.md)

## 开发与贡献

```bash
# 创建功能分支
git switch develop
git pull --ff-only
git switch -c feature/<简短描述>

# 完成修改后运行测试
cd DataRadar && uv run pytest tests/ -q
cd ../PostMaker && uv run pytest tests/ -q -m "not e2e"

# 提交并合并回 develop（示例）
git add .
git commit -m "feat: <变更说明>"
git switch develop
git merge --no-ff feature/<简短描述>
```

提交前请同步更新相关文档，并确认没有把密钥、数据库文件或生成产物加入版本库。

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

## 当前边界与下一步

- 工作台是单用户本地审核工具，当前没有登录、团队权限和并发编辑冲突处理。
- 工作台现在提供“数据源”页面，可直接添加、测试、启用、停用和删除 RSS 源，并在页面中启动采集任务。
- 自动发布适配器尚未实现，批准后的内容需要人工复制或由后续渠道适配器处理。
- 语义搜索需要额外配置 embedding 模型和 API key。
- SQLite 适合本地开发和小规模单机使用；多进程或高并发场景应切换 PostgreSQL。
- 后续优先方向是工作区隔离、任务队列和更多发布渠道适配器，详见 [路线图](docs/roadmap.md)。

## 测试

```bash
cd DataRadar
uv run pytest tests/ -v

cd ../PostMaker
uv run pytest tests/ -v -m "not e2e"
```

E2E 测试需要运行中的 DataRadar API、真实模型配置和额外服务。测试策略见 [测试指南](docs/testing.md)。

## 安全提示

- 不要把 API key 写进 `config.yaml`、README、日志、测试快照或提交记录。
- 分享项目或备份时，先检查 `output/` 中是否包含敏感内容。
- 对外部署 DataRadar API 前，请配置认证、CORS、限流和反向代理；当前默认配置适合本地开发。
