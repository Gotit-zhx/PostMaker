# DataRadar → PostMaker 完整链路审计报告

审计日期：2026-10-30

## 结论

本地 SQLite MVP 已具备从可视化 RSS 配置到内容审核导出的功能闭环：网页可以添加、测试、启停和删除 RSS 源，启动采集并查看状态；素材可由工作台读取，生成草稿后可编辑、修订、批准并导出 Markdown。工作台默认支持匿名开发模式，也可以启用账号、CSRF 和按用户隔离的 SQLite workspace。

2026-10-30 又使用公开 Compose、RSSHub 内网服务和低成本 DeepSeek 模型完成了一次真实用户链路：注册账号、启用 Solidot 推荐来源、采集素材、生成待审核草稿、生成通用平台适配稿并导出 ZIP 发布包。生产级 PostgreSQL、pgvector、Playwright 和多实例部署仍需单独验收。

## 实际验证链路

使用临时 SQLite 数据库和本机临时 RSS HTTP 服务验证数据源配置、RSS 解析、采集任务和内容 API：

```text
GET /health → POST /api/v1/sources/rss/test → POST /api/v1/sources/rss
→ POST /api/v1/collect → GET /api/v1/collect/status → GET /api/v1/content
```

Smoke test 最终确认本机 RSS 条目写入 SQLite，并由内容 API 返回。草稿的生成、编辑、批准、修订恢复和导出由工作台 HTTP 集成测试验证，生成器在测试中使用 mock，不访问模型服务。

### 2026-10-30 真实用户体验补充

本次使用公开部署编排 `docker-compose.public.yml`，通过临时账号完成以下流程：

```text
注册 / 登录 → 启用 RSSHub Solidot → 立即采集 → 浏览素材
→ 选择“科技评论家” → 生成草稿 → 待审核
→ 临时批准 → 生成 generic 适配稿 → 导出 ZIP → 恢复待审核
```

结果：RSSHub 返回 HTTP 200，DataRadar 写入 20 条素材；PostMaker 生成第 2 篇草稿，状态为 `pending_review`，正文约 2544 字符，模型记录为 `deepseek/deepseek-chat`；通用适配接口和 ZIP 发布包均返回 200。文章内容保存在[真实用户体验文章](真实用户体验文章.md)。

启动本地联调环境的命令示例：

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
- 工作台代理测试覆盖：数据源列表、新增和测试 RSS、已保存源测试、启停、删除、立即采集和状态查询。
- DataRadar 数据源测试覆盖：源生命周期、URL 校验、首次访问时从模板初始化配置、`CONFIG_PATH` 读取以及采集重复触发保护。
- 新增 PostMaker → DataRadar 跨服务集成测试，验证工作台代理正确传递 workspace 签名、两个 workspace 的 RSS 源互不可见。
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
DataRadar: 81 passed
PostMaker: 63 passed, 2 deselected (e2e)
compileall: passed
git diff --check: passed
```

临时本机 RSS HTTP smoke test 返回：RSS 测试成功 1 条、采集状态 `completed`、内容列表包含写入的素材。DataRadar API 测试和 PostMaker 工作台测试全量通过。

## 当前限制和风险

- PostgreSQL 路径只完成静态检查和单元测试，没有在本机启动真实 PostgreSQL/pgvector。
- Redis 未配置时健康检查会显示 `redis: unavailable`，但本地 API 仍可工作；生产部署需要 Redis 或调整健康探针策略。
- 语义搜索需要配置 embedding 模型和 API key，本次真实体验没有启用 embedding；文章生成使用了低成本对话模型。
- 工作台支持注册登录、CSRF 和 SQLite workspace 隔离，并已实现发布前的平台适配与来源图片复用；团队权限、并发编辑冲突处理、周期性来源健康检查和平台导出包仍未实现，当前版本仍不适合作为面向公众的托管 SaaS 直接开放。
- 认证模式下，数据源配置和素材数据库按 workspace 持久化，采集状态仍保存在 DataRadar 单进程内存；Docker Compose 已固定为单 worker，多 worker 部署需要先接入共享任务队列和持久化状态。
- SQLite 适合单机开发和小规模部署；PostgreSQL 当前仍是单库模型，正式多租户部署前需要加入 workspace 字段或独立 schema。
- `mark_used` 当前只记录素材与 persona 的关系，尚未在列表响应中展示“已使用”状态。
- RSSHub 路由依赖上游站点稳定性，推荐来源仍应保留“先测试再启用”的提示；不同路由可能随上游改版失效。

## 后续改造优先级

### P0：先保证可运营

1. 增加 DataRadar 与 PostMaker 的请求限流、敏感配置检查和审计日志，禁止 API key 出现在日志和导出文件中。
2. 为 PostgreSQL、Redis 和 pgvector 增加 Docker smoke test，并把健康检查纳入部署流水线。
3. 为采集任务增加失败重试、单源超时、失败源统计和告警。
4. 给 `mark_used` 增加查询接口或返回字段，避免重复生产相同素材/persona 草稿。

### P1：提高商业和技术价值

1. 建立素材评分和 persona 匹配解释：展示为什么推荐某条素材、使用哪些标签和重要性分数。
2. 把审核工作台扩展为内容生产流水线：模板、批量生成、批量审核、发布队列、失败重试和操作审计。
3. 继续扩展多渠道适配器和导出包，例如企业内部知识库；统一 Markdown 中间格式，再由渠道适配器处理长度、图片和排版。
4. 增加质量评估：事实引用、重复率、标题吸引力、persona 风格一致性和人工评分，并把结果用于模型路由。
5. 引入低成本模型路由：低重要性素材使用便宜模型，高重要性素材才使用高质量模型；二阶段 refine 默认关闭。

### P2：形成可复用产品能力

1. 将 RSS 源、标签体系、persona、提示词和输出渠道做成可配置插件。
2. 增加团队空间、权限、评论、审批流和版本对比。
3. 提供内容数据集导出、回放和离线评测，支持更换模型时进行可重复对比。
4. 增加趋势仪表盘、主题聚类和来源质量分析，形成面向内容团队的情报产品。

## 建议的下一步

公开上线前的 P0 是身份认证和租户隔离、按用户持久化 RSS 与模型配置、秘密管理、SSRF/URL 安全策略、共享采集队列、部署与备份演练。之后再把本地闭环部署成可重复的 Docker Compose 环境、补 PostgreSQL/Redis 集成测试，并实现素材推荐解释、重复生成拦截和发布队列。
