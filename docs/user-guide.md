# PostMaker · DataRadar 操作指南

这是一份面向第一次运行项目使用者的完整操作手册。你可以把它当作从零开始的安装教程，也可以直接跳到需要的章节查命令、查配置或排查问题。

这份指南覆盖：

- 安装两个子项目并选择 SQLite 或 PostgreSQL 运行模式
- 配置 RSS / Web 数据源和可选的 AI 摘要
- 启动 DataRadar API、执行采集、搜索和查看素材
- 配置 PostMaker persona，使用 CLI 或网页工作台生成草稿
- 人工编辑、保存修订、批准、归档和导出 Markdown
- 日常运行、备份、测试和常见故障排查

项目包含两个服务：

- **DataRadar** 负责发现和整理素材，提供 CLI、SQLite/PostgreSQL 存储和 REST API。
- **PostMaker** 负责按 persona 生成内容，提供 CLI、本地输出和审核工作台。

推荐先用 SQLite 完成本地体验，再根据数据量切换 PostgreSQL 和 Redis。整条链路如下：

```text
配置数据源 → 测试 RSS → 立即采集 → 查看 / 搜索素材 → PostMaker 匹配 persona
→ 生成草稿 → 人工编辑 → 批准 → 导出 Markdown
```

### 功能地图

| 任务 | 推荐入口 | 结果 |
|---|---|---|
| 添加或检查 RSS | 工作台“数据源”页面，或 `dataradar source` | 保存、测试并启停数据源 |
| 执行采集 | `dataradar fetch`，或工作台“立即采集” | 将条目和可用全文写入知识库 |
| 找选题 | 工作台“素材发现”，或 `dataradar kb search/trending` | 查看摘要、标签、热度和来源 |
| 生成初稿 | 工作台，或 `postmaker generate` | 生成 Markdown/HTML 或待审核草稿 |
| 人工把关 | 工作台编辑器 | 保存修订、批准或归档 |
| 导出交付 | 工作台导出，或读取 `PostMaker/output/` | 得到可继续发布的 Markdown |

工作台适合完整闭环，CLI 适合批量运行、定时任务和故障排查。两者读取同一套 DataRadar API、persona 和模型配置。

## 阅读路径

如果你只想先跑通一次，按下面的顺序阅读：

1. [准备环境](#1-准备环境)
2. [配置 DataRadar](#2-配置-dataradar)
3. [运行 DataRadar](#3-运行-dataradar)
4. [配置 PostMaker](#5-配置-postmaker)
5. [使用审核工作台完成闭环](#7-使用审核工作台完成闭环)

如果你已经能看到素材，可以直接从 [用 CLI 生成内容](#6-用-cli-生成内容) 开始。当前工作台是单用户本地工具；RSS 源可以在“数据源”页面配置，也可以继续使用 CLI 或 YAML。

## 0. 先理解一次完整操作

一次最小闭环需要两个终端：

```text
终端 A：启动 DataRadar API（保持运行）
终端 B：执行采集 → 启动 PostMaker 工作台 → 浏览器审核
```

最短命令序列如下。详细解释和可选配置见后续章节：

```bash
# 终端 A
cd DataRadar
uv run uvicorn api_server.main:app --host 127.0.0.1 --port 8000

# 终端 B
cd DataRadar
uv run dataradar fetch

cd ../PostMaker
export DATARADAR_API_BASE="http://127.0.0.1:8000"
export AI_API_KEY="your-api-key"
export AI_MODEL="deepseek/deepseek-chat"
uv run postmaker workbench
```

打开 `http://127.0.0.1:8787` 后，选择素材、生成草稿、编辑并批准，最后点击导出 Markdown。模型调用只发生在摘要或生成步骤；采集、存储和浏览素材可以先不配置 AI。

## 1. 准备环境

### 1.1 安装软件

需要 Python 3.12 或更高版本和 uv。检查版本：

```bash
python --version
uv --version
```

如果尚未安装 uv，可以按照官方安装方式安装。仓库中的两个子项目分别管理依赖，因此需要分别同步：

```bash
cd DataRadar
uv sync --all-extras
cd ../PostMaker
uv sync --all-extras
```

网页采集和部分全文提取回退需要 Chromium：

```bash
cd DataRadar
uv run playwright install chromium
```

没有安装 Chromium 时，RSS 采集和已有全文通常仍可工作；只有需要 Playwright 的网页目标或 JS 渲染回退时才会受影响。

### 1.2 目录和数据位置

默认情况下：

- DataRadar 本地数据库由 `DATARADAR_SQLITE_PATH` 指定；未指定时使用项目默认的 SQLite 路径。
- PostMaker CLI 输出到 `PostMaker/output/`。
- PostMaker 工作台草稿数据库默认是 `PostMaker/output/workbench.sqlite3`。

建议开发时显式指定路径，便于备份和清理：

```bash
export DATARADAR_SQLITE_PATH="$PWD/DataRadar/output/dataradar.sqlite3"
export POSTMAKER_WORKBENCH_DB="$PWD/PostMaker/output/workbench.sqlite3"
```

## 2. 配置 DataRadar

### 2.1 从模板开始

```bash
cd DataRadar
cp config/config.example.yaml config/config.yaml
```

`config/config.yaml` 主要配置以下内容：

| 配置段 | 用途 |
|---|---|
| `app` | 时区等基础设置 |
| `rss.feeds` | RSS 源列表、启用状态和保留天数 |
| `storage` | 本地存储目录和保留策略 |
| `ai` | 摘要模型、API 地址、超时和 token 上限 |
| `web_scraper` | Playwright 网页采集目标 |
| `knowledge_base` | PostgreSQL、Redis 和 embedding |
| `advanced` | 请求间隔、超时和代理 |

如果配置文件不存在，程序会回退到示例配置；正式使用时仍建议复制一份并按环境修改。

### 2.2 配置 RSS 源

每个源至少需要 `id`、`name` 和 `url`：

```yaml
rss:
  enabled: true
  feeds:
    - id: "hacker-news"
      name: "Hacker News"
      url: "https://hnrss.org/frontpage"
      enabled: true
      max_age_days: 1
```

`max_age_days` 只影响查询时的新鲜度过滤，采集阶段会尽量把源返回的内容写入库。源的增删改也可以通过 CLI 完成：

```bash
uv run dataradar source list
uv run dataradar source add rss "https://example.com/feed.xml" --id example --name "Example"
uv run dataradar source test example
uv run dataradar source disable example
uv run dataradar source enable example
uv run dataradar source remove example
```

网页源需要 CSS 选择器：

```bash
uv run dataradar source add web "https://example.com/news" \
  --id example-web \
  --list-selector "article" \
  --title-selector "h2" \
  --link-selector "a"
```

### 2.3 配置 AI 摘要（可选）

DataRadar 可以在采集时生成摘要、分类、标签和重要性评分。使用环境变量比把密钥写进 YAML 更安全：

```bash
export AI_API_KEY="your-api-key"
export AI_MODEL="deepseek/deepseek-chat"
# 兼容 OpenAI 协议的第三方服务可设置：
# export AI_API_BASE="https://api.example.com/v1"
```

LiteLLM 模型名使用 `provider/model` 格式。若服务商是 OpenAI 协议兼容接口，通常使用 `openai/实际模型名`，并设置 `AI_API_BASE`。

为了控制成本，可以按以下顺序运行：

1. 先关闭 AI 摘要，仅确认采集、存储和 API 正常。
2. 用低价模型做批量摘要和初稿。
3. 只有需要更高质量时才在 PostMaker 使用 `--refine`。

不要把 API key 提交到 Git，也不要把 key 写入日志、报告或导出的 Markdown。

### 2.4 数据源地址的安全限制

网页工作台和 DataRadar API 会拒绝 localhost、内网或保留 IP、非 HTTP(S) 协议、非默认端口以及包含用户名密码的 URL，并逐跳检查 HTTP 重定向。这个限制用于保护部署主机；如果某个公开 RSS 源依赖非标准端口或内部跳转，应先换用公开入口或在可信网络中通过代理访问。

### 2.5 配置网页采集和代理

`web_scraper.enabled` 控制 Playwright 网页采集；`advanced.rss.use_proxy` 和 `advanced.rss.proxy_url` 控制 RSS 请求代理。代理配置示例：

```yaml
advanced:
  rss:
    use_proxy: true
    proxy_url: "http://127.0.0.1:7890"
```

先用 `source test` 验证单个源，再执行完整采集，避免一个失效源拖慢排查。

## 3. 运行 DataRadar

### 3.1 启动 API（SQLite 模式）

在终端 A：

```bash
cd DataRadar
export DATARADAR_SQLITE_PATH="$PWD/output/dataradar.sqlite3"
uv run uvicorn api_server.main:app --host 127.0.0.1 --port 8000
```

确认健康检查：

```bash
curl http://127.0.0.1:8000/health
```

API 进程保持运行，后续 PostMaker 会通过它获取素材。

### 3.2 运行一次采集

在终端 B：

```bash
cd DataRadar
uv run dataradar fetch
```

常用查看命令：

```bash
uv run dataradar status
uv run dataradar rss --status
uv run dataradar rss --days 3 --limit 20 --summary
uv run dataradar kb stats
```

若默认日期没有结果，先查看 `status` 和 `kb list`。当前 API 和 CLI 会优先使用本地库中最新的采集日期，适合首次运行或补采历史数据。

### 3.3 在工作台配置 RSS 并启动采集

启动 DataRadar API 和 PostMaker 工作台后，打开 `http://127.0.0.1:8787`，点击左侧“数据源”。这里可以完成一条 RSS 源的完整配置：

1. 填写 RSS 地址；名称和源 ID 可以留空，系统会根据地址生成默认值。
2. 点击“测试 RSS”，确认能够读取到条目。
3. 点击“保存数据源”，源会写入 DataRadar 配置并默认启用。
4. 点击“立即采集”，页面会显示运行中、完成或失败状态；采集完成后回到“素材发现”刷新列表。

已保存的源支持再次测试、启用、停用和删除。工作台通过 PostMaker 代理访问 DataRadar，因此浏览器只需要访问 `8787` 端口。采集状态保存在当前 DataRadar 进程内，适合单实例本地运行；多 worker 部署前应先增加共享任务队列和权限隔离。

### 3.4 查询和搜索素材

```bash
uv run dataradar kb list --limit 20
uv run dataradar kb list --type text --limit 20
uv run dataradar kb search "大模型"
uv run dataradar kb trending --limit 20
uv run dataradar kb get 42
```

语义搜索需要额外配置 embedding：

```bash
export EMBED_MODEL="text-embedding-3-small"
export EMBED_API_KEY="your-embedding-key"
uv run dataradar kb semantic "适合写 AI 行业分析的素材" --limit 10
```

没有 embedding 配置时，使用关键词搜索即可。

### 3.5 定时采集

前台运行内置调度器：

```bash
uv run dataradar schedule --interval 240
```

这会每 240 分钟运行一次采集。长期运行建议使用 systemd、cron 或 Windows 任务计划；可参考 [部署指南](deployment.md) 中的示例。

## 4. 使用 DataRadar REST API

基础地址默认为 `http://127.0.0.1:8000`。常用接口：

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 内容列表
curl 'http://127.0.0.1:8000/api/v1/content?limit=10'

# 关键词搜索
curl 'http://127.0.0.1:8000/api/v1/content/search?q=AI&limit=10'

# 热门内容
curl 'http://127.0.0.1:8000/api/v1/content/trending?limit=10'

# 主题趋势
curl 'http://127.0.0.1:8000/api/v1/content/topics/trending?days=3'

# 按分类获取素材包
curl 'http://127.0.0.1:8000/api/v1/content/bundle?category=AI&limit=10'

# 内容详情
curl http://127.0.0.1:8000/api/v1/content/42
```

内容列表使用游标分页：读取响应中的 `meta.next_cursor`，再把它作为下一次请求的 `cursor`。

完整字段、错误码和语义搜索请求体见 [API 参考](api-reference.md)。当前 API 默认没有认证，生产环境应放在带认证和限流的网关后面。

调用数据源管理接口时，RSS 地址必须先通过公开 URL 校验；校验失败通常返回 HTTP 422。采集接口是单实例后台任务，同一进程同时只能运行一个采集任务。

## 5. 配置 PostMaker

### 5.1 设置 DataRadar 地址和模型

PostMaker 的配置文件是 `PostMaker/config/config.yaml`。常用环境变量：

```bash
cd PostMaker
export DATARADAR_API_BASE="http://127.0.0.1:8000"
export DATARADAR_TIMEOUT=15
export AI_API_KEY="your-api-key"
export AI_MODEL="deepseek/deepseek-chat"
```

环境变量会覆盖配置文件中的对应值。工作台和 CLI 使用同一套配置。

### 5.2 查看 persona

```bash
uv run postmaker personas
```

当前 persona 文件位于 `config/personas/`。每个文件由 YAML frontmatter 和 Markdown body 组成：

```yaml
---
id: "tech-reviewer"
name: "科技评论家"
description: "资深科技媒体人"
style:
  tone: "professional_analytical"
  language: "zh-CN"
  length_preference: "long"
interests:
  topics: ["AI", "云计算", "开源"]
  min_importance: 3
---

你是一位资深科技评论家……
```

`interests.topics` 控制主题匹配，`min_importance` 控制最低重要性。修改 persona 后重新运行 `postmaker personas`，确认 YAML 能被正确加载。更多写作策略见 [persona 指南](persona-guide.md)。

## 6. 用 CLI 生成内容

### 6.1 先查看素材

```bash
uv run postmaker materials --trending
uv run postmaker materials --search "AI"
uv run postmaker materials --detail 42
```

### 6.2 预览匹配结果

推荐先 dry-run，确认素材和 persona 的组合：

```bash
uv run postmaker generate --trending --persona tech-reviewer --limit 5 --dry-run
```

`--dry-run` 不调用模型，也不会写入输出文件。

### 6.3 生成初稿

```bash
# 从热门内容生成
uv run postmaker generate --trending --limit 3

# 按主题获取素材
uv run postmaker generate --topic AI --limit 3

# 指定一条素材
uv run postmaker generate --material-id 42 --persona tech-reviewer
```

生成结果默认写入：

```text
PostMaker/output/{日期}/{persona-id}/{标题}.md
PostMaker/output/{日期}/{persona-id}/{标题}.html
```

Markdown 文件带有 `title`、`persona`、`source`、`generated_at` 和 `model` 等 frontmatter；HTML 文件包含内联样式，可直接用浏览器打开。

### 6.4 使用二阶段优化

```bash
uv run postmaker generate --trending --limit 2 --refine
```

Refiner 会增加一次模型调用和 token 消耗。批量生产时建议只对重要素材或人工筛选后的少量草稿开启。

### 6.5 查看历史和去重

配置 `POSTGRES_DSN` 后，PostMaker 会保存素材、人设和草稿记录：

```bash
export POSTGRES_DSN="postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base"
uv run postmaker history
uv run postmaker history --persona tech-reviewer
```

生成前会检查已有的素材 + persona 组合，已生成的组合会被跳过。未配置 PostgreSQL 时仍可生成文件，但 `history` 和跨进程去重不可用。

## 7. 使用审核工作台完成闭环

### 7.1 启动

先确保 DataRadar API 已运行，再启动工作台：

```bash
cd PostMaker
export DATARADAR_API_BASE="http://127.0.0.1:8000"
export AI_API_KEY="your-api-key"
export AI_MODEL="deepseek/deepseek-chat"
uv run postmaker workbench
```

打开 <http://127.0.0.1:8787>。如果端口冲突：

```bash
uv run postmaker workbench --host 127.0.0.1 --port 9000
```

检查工作台服务：

```bash
curl http://127.0.0.1:8787/api/health
```

### 7.2 页面操作流程

1. 在素材列表选择“热门”或“最近”，点击一条素材查看详情。
2. 选择一个 persona。列表中的主题兴趣可以帮助判断匹配是否合理。
3. 点击生成草稿。工作台会读取 DataRadar 详情，调用模型生成正文，并把草稿保存到本地 SQLite。
4. 在编辑区修改标题和正文，保存后会创建一条修订记录。
5. 确认事实、来源、标题和格式后，将状态改为“已批准”。不需要的草稿可以归档。
6. 在已批准草稿详情页导出 Markdown。

工作台的状态流转是：

```text
待审核 ──→ 已批准 ──→ 导出 Markdown
   └────→ 已归档
```

生成草稿成功落库后，工作台会尝试调用 DataRadar 的 `mark_used` 接口记录素材和 persona 的使用关系。标记失败不会删除已经保存的草稿，但需要在日志中排查 DataRadar 连接。

### 7.3 修订和恢复

工作台每次保存都会创建修订。可以在草稿详情中查看修订列表，并选择某个版本恢复。恢复本身也会产生新的当前版本，便于继续编辑。

### 7.4 导出规则

只有 `approved` 状态的草稿可以通过接口导出：

```bash
curl -OJ http://127.0.0.1:8787/api/drafts/1/export.md
```

导出的 Markdown 会保留来源 URL、persona、模型和生成时间，适合作为人工发布前的中间文件。工作台不会直接发布到外部平台。

## 8. PostgreSQL、Redis 和 Docker

本地链路稳定后，可以启动基础设施：

```bash
cd DataRadar/docker
cp .env.example .env
docker compose up postgres redis -d
```

如果需要 RSSHub：

```bash
docker compose up postgres redis rsshub -d
```

如果要运行 Compose 中的 API 和 Nginx：

```bash
docker compose up -d
```

默认服务：

| 服务 | 端口 | 用途 |
|---|---:|---|
| PostgreSQL | 5432 | 知识库、全文索引、向量扩展 |
| Redis | 6379 | API 和 RSSHub 缓存 |
| RSSHub | 1200 | 将部分站点转换为 RSS |
| Nginx/API | 8000 | 对外提供 DataRadar API |

生产环境至少应修改 PostgreSQL 密码，并限制端口访问。`ALLOWED_ORIGINS` 用于配置 CORS；语义搜索还需要 `EMBED_MODEL`、`EMBED_API_KEY` 和可选的 `EMBED_API_BASE`。

## 9. 常见问题

### API 返回空列表

先执行：

```bash
uv run dataradar status
uv run dataradar kb stats
uv run dataradar kb list --limit 20
```

确认 API 进程和采集命令使用的是同一个 `DATARADAR_SQLITE_PATH`。如果库中有数据但“今天”没有结果，使用 `kb list` 或指定日期查询。

### PostMaker 提示无法连接 DataRadar

检查：

```bash
curl http://127.0.0.1:8000/health
echo "$DATARADAR_API_BASE"
```

确认工作台所在终端设置了正确的 `DATARADAR_API_BASE`，并检查 `DATARADAR_TIMEOUT` 是否过短。

### 生成提示没有配置 AI

同时设置：

```bash
export AI_API_KEY="your-api-key"
export AI_MODEL="provider/model-name"
```

如果使用自定义 OpenAI 兼容接口，再设置 `AI_API_BASE`。不要把 key 直接提交到配置文件。

### 采集速度慢或单个源失败

先执行 `dataradar source test <id>`。再检查 RSS 超时、代理和 `advanced.rss.request_interval`。网页采集通常比 RSS 慢，应减少目标数量并设置合理的域名间隔。

### 语义搜索返回 503

这表示 embedding 没有配置或没有启用。先使用 `kb search` 关键词搜索；需要语义搜索时配置 embedding 模型和密钥，并确认模型供应商支持 embeddings。

### 工作台导出返回 409

只有已批准的草稿可以导出。先在编辑页保存内容，再把状态改为“已批准”。

### 运行测试

```bash
cd DataRadar
uv run pytest tests/ -v

cd ../PostMaker
uv run pytest tests/ -v -m "not e2e"
```

E2E 测试需要运行中的 DataRadar、真实模型配置和额外服务。测试分层说明见 [测试指南](testing.md)。

## 10. 备份和清理

单机模式至少备份：

- `DataRadar/output/` 中的 SQLite 数据库和采集结果。
- `PostMaker/output/` 中的 Markdown、HTML、工作台 SQLite 数据库。
- `config/config.yaml` 和 `config/personas/`（不包含 API key）。

清理缓存或重新开始本地试验前，先停止 API 和工作台，再移动或备份对应 SQLite 文件。PostgreSQL 模式应使用 `pg_dump`，Redis 数据可以按需重建。

## 11. 推荐的日常工作流

每天或每次选题可以按以下顺序执行：

```bash
# 1. 采集
cd DataRadar && uv run dataradar fetch

# 2. 查看趋势
uv run dataradar kb trending --limit 20

# 3. 预览匹配
cd ../PostMaker
uv run postmaker generate --trending --limit 10 --dry-run

# 4. 生成少量初稿
uv run postmaker generate --trending --limit 3

# 5. 打开工作台进行人工审核
uv run postmaker workbench
```

先确认素材来源和事实，再批准和导出。对高重要性素材保留人工核验，对低重要性素材使用低成本模型和较短输出，可以控制成本并提高吞吐量。
