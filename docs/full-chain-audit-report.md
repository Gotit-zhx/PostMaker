# DataRadar → PostMaker 完整链路审计报告

审计日期：2026-10-30

## 结论

本地 SQLite 链路已经可以闭环运行：采集数据写入 DataRadar，REST API 能够列表、详情、搜索、趋势和统计，PostMaker 能读取素材、生成草稿、保存修订、人工批准并导出 Markdown。生成环节使用 mock 验证，没有调用真实 AI API，也没有读取或保存用户提供的 API key。

生产级 PostgreSQL、Redis、pgvector、Playwright 和真实模型调用没有在本次环境启动验证，部署前仍需单独验收。

## 实际验证链路

使用临时 SQLite 数据库和 fixture RSS 数据验证采集器编排（关闭真实网络抓取、AI 和 Playwright），再启动 API 与工作台：

```bash
DATARADAR_SQLITE_PATH=/tmp/dataradar-e2e.sqlite3 \
PYTHONPATH=. ../PostMaker/.venv/bin/uvicorn api_server.main:app \
  --host 127.0.0.1 --port 18000

POSTMAKER_WORKBENCH_DB=/tmp/postmaker-e2e.sqlite3 \
DATARADAR_API_BASE=http://127.0.0.1:18000 \
.venv/bin/python -m postmaker workbench \
  --host 127.0.0.1 --port 18787
```

已通过 HTTP 验证：

- DataRadar `/health`、内容列表、详情、搜索、热门、主题趋势、素材包、统计和 `mark_used`。
- PostMaker `/api/health`、persona 列表、素材列表、素材详情和草稿列表。
- `DataCollector.run()` 执行 fixture 采集、SQLite 持久化并关闭存储连接；随后 DataRadar API `/api/v1/content` 能读取该采集结果。
- 工作台测试覆盖：生成草稿 → 待审核 → 编辑 → 批准 → Markdown 导出 → 修订恢复。
- `dataradar rss --status`、`--search` 和默认查询在 SQLite 模式下均可运行。

## 已修复问题

### DataRadar

- 没有 `POSTGRES_DSN` 时，采集器和 API 统一使用 SQLite；路径可由 `DATARADAR_SQLITE_PATH` 指定。
- 内容、热门、素材包、主题趋势和统计趋势在未传日期时，会优先使用本地库最新采集日期，避免“当天没有数据导致空列表”。
- RSS 多媒体字段能够从解析器传递到存储和 API，包括内容类型、封面、媒体地址、时长和 enclosure 信息。
- `DataCollector.run()` 使用 `try/finally` 释放存储资源。
- 配置文件不存在时自动回退到 `config.example.yaml`。
- `dataradar rss` 查询命令修复了异步方法未等待的问题，并补充 SQLite 查询分支。此前 `rss --status` 会因 coroutine 无法 JSON 序列化而失败。
- 新增 ETL transformer，修复已有测试和本地导入缺失模块的问题。

### PostMaker

- 增加本地审核工作台，完成素材发现、persona 选择、草稿生成、编辑、审核、修订恢复和 Markdown 导出。
- 增加 `DATARADAR_API_BASE` 与 `DATARADAR_TIMEOUT` 环境变量覆盖，便于服务分离部署和联调。
- 草稿成功落库后调用 DataRadar `mark_used`；标记失败只记录日志，不影响已保存草稿，避免生成结果丢失。
- 工作台草稿和修订使用 SQLite 持久化，支持通过 `POSTMAKER_WORKBENCH_DB` 指定路径。

## 测试结果

```text
DataRadar: 56 passed
PostMaker: 53 passed, 2 skipped
compileall: passed
git diff --check: passed
```

真实 HTTP 联调中，DataRadar `/api/v1/content` 和 PostMaker `/api/materials` 返回了同一批素材；`mark_used` 返回 200，统计和趋势默认日期为 `2026-10-30`。

## 当前限制和风险

- PostgreSQL 路径只完成静态检查和单元测试，没有在本机启动真实 PostgreSQL/pgvector。
- Redis 未配置时健康检查会显示 `redis: unavailable`，但本地 API 仍可工作；生产部署需要 Redis 或调整健康探针策略。
- 语义搜索需要配置 embedding 模型和 API key，本次没有调用模型。
- 工作台目前是单用户本地审核工具，没有登录、权限、并发编辑冲突处理和发布平台适配。
- SQLite 适合单机开发和小规模部署；多进程高并发采集应切换 PostgreSQL。
- `mark_used` 当前只记录素材与 persona 的关系，尚未在列表响应中展示“已使用”状态。

## 后续改造优先级

### P0：先保证可运营

1. 增加 DataRadar 与 PostMaker 的鉴权、请求限流和敏感配置检查，禁止 API key 出现在日志和导出文件中。
2. 为 PostgreSQL、Redis 和 pgvector 增加 Docker smoke test，并把健康检查纳入部署流水线。
3. 为采集任务增加失败重试、单源超时、失败源统计和告警。
4. 给 `mark_used` 增加查询接口或返回字段，避免重复生产相同素材/persona 草稿。

### P1：提高商业和技术价值

1. 建立素材评分和 persona 匹配解释：展示为什么推荐某条素材、使用哪些标签和重要性分数。
2. 把审核工作台扩展为内容生产流水线：模板、批量生成、批量审核、发布队列、失败重试和操作审计。
3. 增加多渠道适配器，例如公众号、知乎、小红书、LinkedIn 和企业内部知识库；统一 Markdown 中间格式，再由渠道适配器处理长度、图片和排版。
4. 增加质量评估：事实引用、重复率、标题吸引力、persona 风格一致性和人工评分，并把结果用于模型路由。
5. 引入低成本模型路由：低重要性素材使用便宜模型，高重要性素材才使用高质量模型；二阶段 refine 默认关闭。

### P2：形成可复用产品能力

1. 将 RSS 源、标签体系、persona、提示词和输出渠道做成可配置插件。
2. 增加团队空间、权限、评论、审批流和版本对比。
3. 提供内容数据集导出、回放和离线评测，支持更换模型时进行可重复对比。
4. 增加趋势仪表盘、主题聚类和来源质量分析，形成面向内容团队的情报产品。

## 建议的下一步

先把本地闭环部署成一个可重复的 Docker Compose 环境，再补 PostgreSQL/Redis 集成测试；随后实现“素材推荐解释 + 重复生成拦截 + 发布队列”三项能力。这三项能同时提升可靠性、人工效率和产品可售卖性。
