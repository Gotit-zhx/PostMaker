# DataRadar 工作交接文档

## 一、系统架构

### 数据流

```
RSS 源（15+）─────────────────┐
  直接 RSS + RSSHub 代理      │
                              ├──→ ③全文提取 → ④AI 摘要 → ⑤SQLite (output/)
Playwright 网页采集（可选）────┘                                    │
  ②Product Hunt / GitHub Trending                            ⑥ETL 管道
                                                                   │
                                                        PostgreSQL + pgvector
                                                                   │
                                                              Redis 缓存
                                                                   │
                                                     ┌──────────────────────┐
                                                     │  FastAPI REST API    │
                                                     │  DataRadar CLI       │
                                                     └──────────────────────┘
```

### 采集管道 6 阶段

1. **RSS 全量采集**：feedparser 解析，全量入库不过滤
2. **Playwright 网页采集**（可选）：CSS 选择器提取 + AI 回退
3. **三引擎全文提取**：Trafilatura → Playwright → Jina Reader
4. **AI 摘要生成**：LiteLLM 调用 LLM 生成 ~200 token 摘要
5. **存入 SQLite**：本地持久化（含 full_text + ai_summary）
6. **ETL → PostgreSQL**：写入知识库，支持全文搜索

入口：`dataradar/collector.py` → `DataCollector.run()`

---

## 二、目录结构与模块职责

```
dataradar/                          # 主包
├── __init__.py                     # 版本号 __version__
├── __main__.py                     # CLI 入口（argparse 子命令分发）
├── collector.py                    # DataCollector 采集管道（核心入口）
├── context.py                      # AppContext：配置→对象的统一工厂
├── source_manager.py               # ruamel.yaml 读写 config.yaml（保留注释）
├── cli/                            # CLI 子命令处理
│   ├── collect.py                  # fetch, status
│   ├── rss.py                      # RSS 查询/搜索
│   ├── source.py                   # 源管理 CRUD
│   ├── kb.py                       # 知识库操作
│   └── read.py                     # 文章阅读
├── tools/                          # 业务逻辑（被 CLI 和 services 调用）
│   ├── knowledge.py                # KB 语义/全文搜索实现
│   └── article_reader.py           # Jina Reader 文章阅读
├── services/                       # 数据访问层
│   ├── data_service.py             # RSS 数据查询
│   ├── parser_service.py           # SQLite RSS 解析
│   ├── cache_service.py            # LRU 缓存
│   └── api_client.py              # KB API HTTP 客户端
├── ai/                             # AI 模块
│   ├── client.py                   # AIClient（LiteLLM 封装）
│   ├── summarizer.py               # ContentSummarizer（并发摘要生成）
│   ├── filter.py                   # AI 智能过滤（可选）
│   ├── filter_pipeline.py          # 过滤管道
│   └── prompt_loader.py            # 提示词模板加载（config/ 子目录）
├── crawler/
│   ├── rss/
│   │   ├── fetcher.py              # RSSFetcher：批量 RSS 抓取
│   │   └── parser.py               # feedparser 解析 → RSSItem
│   └── web/
│       └── scraper.py              # PlaywrightScraper：网页列表采集
├── enricher/
│   └── extractor.py                # ArticleExtractor：三引擎并行全文提取
├── core/
│   ├── loader.py                   # load_config()：YAML → 大写 key 字典
│   ├── data.py                     # 数据模型
│   └── analyzer.py                 # 分析工具
├── storage/
│   ├── base.py                     # RSSItem/RSSData 数据类
│   ├── manager.py                  # StorageManager 工厂
│   ├── local.py                    # LocalStorage（SQLite）
│   ├── remote.py                   # RemoteStorage（S3 兼容）
│   ├── sqlite_*.py                 # SQLite Mixin 系列
│   ├── schema.sql                  # 主 schema
│   └── rss_schema.sql              # RSS 表 schema
└── utils/
    ├── time.py                     # 时区处理
    ├── url.py                      # URL 工具
    ├── date_parser.py              # 自然语言日期解析
    ├── validators.py               # 参数验证
    └── errors.py                   # 自定义异常（AppError 基类）

knowledge_base/                     # PostgreSQL 知识库层
├── schema.sql                      # DDL（pgvector + pg_trgm 扩展）
├── db.py                           # asyncpg 连接池管理
├── cache.py                        # Redis 分级 TTL 缓存
├── repository.py                   # CRUD 操作
└── etl/
    ├── pipeline.py                 # ETLPipeline：SQLite → PostgreSQL
    └── embedder.py                 # BatchEmbedder：LiteLLM 向量嵌入

api_server/                         # FastAPI REST 服务
├── main.py                         # App 创建 + 路由注册
├── schemas.py                      # Pydantic 请求/响应模型
└── routers/                        # content, knowledge, stats

config/
├── config.yaml                     # 主配置文件
├── etl/                            # ETL 提示词模板
├── web_scraper/                    # 网页采集 AI 提取提示词
├── ai_filter/                      # AI 过滤 Prompt
└── frequency_words.txt             # 关注词

docker/
├── docker-compose.yml              # PostgreSQL + Redis + RSSHub + API + Nginx
├── Dockerfile.api                  # FastAPI 镜像
├── nginx.conf                      # 反向代理配置
└── .env                            # Docker 环境变量
```

---

## 三、配置体系

### 加载链路

```
config/config.yaml
    ↓ PyYAML 读取
core/loader.py → load_config()
    ↓ 小写 key → 大写 key 转换
返回 Dict[str, Any]（所有 key 都是大写）
    ↓
context.py → AppContext(config) 初始化各模块
```

**关键机制**：`loader.py` 将 YAML 中的小写 key 转换为大写。例如：

- `knowledge_base.embedding.enabled` → `config["KNOWLEDGE_BASE"]["EMBEDDING"]["ENABLED"]`
- `ai.api_key` → `config["AI"]["API_KEY"]`
- `web_scraper.proxy_url` → `config["WEB_SCRAPER"]["PROXY_URL"]`

ETL pipeline 的 `from_config()` 方法也必须使用大写 key 访问配置，这是一个容易出错的地方。

### 源管理

`source_manager.py` 使用 `ruamel.yaml`（而非 PyYAML）读写 config.yaml，目的是**保留 YAML 中的注释和格式**。其他地方用 PyYAML 只读加载。

---

## 四、关键实现细节

### 4.1 三引擎全文提取（`enricher/extractor.py`）

三阶段并行架构：

```
阶段 1: asyncio.gather + Semaphore(20) 并发 Trafilatura
  → 失败的 URL 进入阶段 2
阶段 2: 共享 Playwright 浏览器 + Semaphore(3) 并发 tab
  → 仍然失败的 URL 进入阶段 3
阶段 3: asyncio.gather + Semaphore(5) 并发 Jina API
```

注意事项：
- Trafilatura 不直接下载网页（它内置的 `fetch_url()` 不支持代理），改为 `requests.get()` 先下载 HTML（带代理），再调用 `trafilatura.extract(html)`
- Playwright 使用 `domcontentloaded`（而非 `networkidle`），避免 SPA 站点超时
- Jina Reader 有频率限制，通过 `_jina_min_interval` 和 Semaphore 控制

### 4.2 AI 摘要生成（`ai/summarizer.py`）

- `ThreadPoolExecutor(max_workers=10)` 并发调用 LLM
- 提示词模板在 `config/etl/summarize_prompt.txt`
- `_summarize_one()` 取 `full_text`（优先）或 `summary`（RSS 原文摘要）前 3000 字符

### 4.3 LiteLLM 集成（`ai/client.py`）

- `litellm.suppress_debug_info = True`：必须设置，否则每次调用都会打印 "Give Feedback" 信息
- `temperature`：部分模型（如 gpt-5）要求固定为 1.0，否则报错
- `max_tokens`：设为 0 时不发送此参数（某些 API 不支持）
- `fallback_models`：备用模型列表，主模型失败时自动切换

### 4.4 Playwright 网页采集（`crawler/web/scraper.py`）

- `playwright-stealth`：隐藏自动化特征，减少被检测概率
- 域名限速：`min_domain_interval` 秒（默认 10s）
- 随机 viewport 尺寸（1280-1920 × 800-1080）和页面停留时间
- 两种提取模式：
  1. CSS 选择器模式（配置 `list_selector` + `title_selector`）
  2. AI 提取模式（未配置选择器时，发送 HTML 给 AI 解析）

### 4.5 代理传递链路

```
config.yaml advanced.rss.proxy_url
    ↓ loader.py
config["RSS"]["PROXY_URL"]
    ↓ collector.py
├── RSSFetcher（RSS 抓取）
├── ArticleExtractor（全文提取：Trafilatura / Playwright / Jina）
│   └── _sync_download_html() 使用 requests.get(proxies=...)
└── PlaywrightScraper 使用独立的 web_scraper.proxy_url
```

### 4.6 ETL 管道（`knowledge_base/etl/pipeline.py`）

- `ETLPipeline.from_config(config)`：从大写 key 字典构建
- 从 SQLite `output/` 目录读取当天数据
- 写入 PostgreSQL（含 embedding 向量，如果启用）
- 使用 `asyncpg` 异步连接池

---

## 五、数据库 Schema

### SQLite（本地存储）

`rss_items` 表关键字段：

| 字段 | 说明 |
|------|------|
| `summary` | RSS feed 原文自带的摘要（feedparser 解析） |
| `ai_summary` | AI 大模型生成的结构化摘要 |
| `full_text` | 三引擎提取的文章全文 |

**summary 和 ai_summary 不是冗余字段**：前者来自 RSS 源本身（通常很短或为空），后者是 AI 基于全文生成的高质量摘要。

### PostgreSQL（知识库）

见 `knowledge_base/schema.sql`：
- `pgvector` 扩展：向量相似度搜索
- `pg_trgm` 扩展：模糊全文搜索
- `content` 表：主内容表
- `knowledge_entries` 表：聚合知识条目

---

## 六、已知问题与 TODO

### 已知问题

1. **Embedding 端点不可用**：当前使用的 API 代理（`sub.moder.cc`）不支持 `/embeddings` 端点，`knowledge_base.embedding.enabled` 设为 `false`。切换到支持 embedding 的 API（如 OpenAI 官方）后，改为 `true` 即可启用语义搜索。

2. **无内置定时调度**：调度模块已移除。需通过外部方式定期触发：
   ```bash
   # crontab 示例：每 6 小时采集一次
   0 */6 * * * cd /path/to/DataRadar && python -m dataradar fetch >> /var/log/dataradar.log 2>&1
   ```

3. **部分 RSS 源已失效**：
   - BBC Technology：通过代理时 SSL 握手失败
   - Reuters Technology：已关闭公开 RSS 服务
   - Anthropic News：RSS feed 返回 404
   
   这些源在 `config.yaml` 中已标记 `enabled: false` 并注明原因。

4. **RSSHub 路由限制**：Reddit、YouTube、ProductHunt 路由需在 RSSHub 中配置对应 API Key。已禁用的路由在 config.yaml 中有注释说明。

5. **全文提取依赖代理**：无代理时，大量境外站点会因 SSL 连接问题失败。`advanced.rss.use_proxy` 和 `proxy_url` 配置很重要。

### TODO

- [ ] 对接支持 Embedding 的 API，启用 pgvector 语义搜索
- [ ] 添加更多中文数据源
- [ ] 考虑恢复轻量级定时调度（或提供 systemd timer 模板）
- [ ] 补充单元测试
- [ ] 性能监控：采集耗时、成功率等指标上报

---

## 七、开发环境搭建

### 一键安装（推荐）

```bash
git clone <repo-url> && cd DataRadar

# Mac/Linux
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Windows
scripts\setup.bat
```

### 手动安装

```bash
git clone <repo-url> && cd DataRadar

# 安装 uv（如已安装可跳过）
# Mac/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 同步依赖（自动创建 .venv、安装 Python 3.12+、安装所有依赖）
uv sync --all-extras

# 安装 Playwright 浏览器（全文提取 + 网页采集需要）
uv run playwright install chromium
```

### 启动基础设施

```bash
cd docker
docker compose up postgres redis rsshub -d

# 验证服务
docker compose ps
curl http://localhost:1200           # RSSHub 健康检查
```

### 配置

编辑 `config/config.yaml`：
1. 设置 `ai.api_key` 和 `ai.model`
2. 设置 `advanced.rss.proxy_url`（如需代理）
3. 确认 `knowledge_base.postgres_dsn` 和 `redis_url` 与 Docker 服务匹配

### 运行

```bash
# 查看系统状态
uv run dataradar status

# 运行完整采集管道
uv run dataradar fetch

# 查询已采集数据
uv run dataradar rss --days 1

# 启动 API 服务
uv run uvicorn api_server.main:app --reload --port 8000
```

---

## 八、排错指南

### SSL 连接失败

**症状**：全文提取大量报错 `SSLError` 或 `ConnectionError`

**原因**：境外站点直连 SSL 握手失败

**解决**：确认 `advanced.rss.use_proxy: true` 且 `proxy_url` 指向可用的 HTTP 代理

### LiteLLM 日志刷屏

**症状**：控制台输出大量 `INFO Wrapper: Completed Call` 或 "Give Feedback" 信息

**解决**：确认 `ai/client.py` 中有 `litellm.suppress_debug_info = True`，且 `collector.py` 中将 LiteLLM 和 litellm logger 设为 ERROR 级别

### RSSHub 502 / 连接失败

**症状**：RSSHub 源全部返回 502 或连接超时

**原因**：
1. config.yaml 中 RSSHub URL 使用了 Docker 内部地址 `rsshub:1200`，但本地运行时应为 `localhost:1200`
2. RSSHub Docker 服务未启动

**解决**：确认 URL 为 `http://localhost:1200/...`，且 `docker compose ps` 显示 rsshub 正在运行

### ETL 配置读取失败

**症状**：ETL 阶段报 KeyError 或读取到空值

**原因**：`loader.py` 将 YAML 小写 key 转为大写，ETL 代码必须用大写 key 访问

**解决**：检查 `knowledge_base/etl/pipeline.py` 中 `from_config()` 是否使用了正确的大写 key（如 `KNOWLEDGE_BASE` 而非 `knowledge_base`）

### Playwright 超时

**症状**：网页采集报 `TimeoutError`

**原因**：使用了 `networkidle` 等待策略，SPA 站点永远不会达到 network idle

**解决**：确认 `scraper.py` 和 `extractor.py` 中 `wait_until` 为 `"domcontentloaded"`

### 数据采集为 0 条

**症状**：运行 `dataradar fetch` 后显示 0 条数据

**排查顺序**：
1. `dataradar status` — 确认 RSS 已启用且有启用的源
2. 检查代理是否可用
3. `dataradar source test <id>` — 测试单个源
4. 查看 `config.yaml` 中是否所有源都 `enabled: false`

---

*文档更新日期：2026-04-17*
