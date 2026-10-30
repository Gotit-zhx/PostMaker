# DataRadar REST API 参考

**基础 URL**：`http://localhost:8000`

**认证**：当前版本不需要认证。生产环境建议通过 Nginx 或网关添加认证层。

**内容类型**：所有请求和响应使用 `application/json`。

---

## 数据源与采集接口

这些接口支持工作台中的 RSS 自助配置。配置写回 DataRadar 当前实例的 YAML 文件，采集任务也在当前进程内运行。

### GET /api/v1/sources

返回 RSS 和 Web 数据源：

```json
{"items": [{"kind": "rss", "id": "hacker-news", "name": "Hacker News", "url": "https://hnrss.org/frontpage", "enabled": true, "max_age_days": 1}], "count": 1}
```

### POST /api/v1/sources/rss

添加 RSS 源。`url` 必须使用 `http://` 或 `https://`；`id` 可省略。

```json
{"url": "https://example.com/feed.xml", "name": "Example", "id": "example", "max_age_days": 3, "enabled": true}
```

成功返回 `201`；重复 ID 返回 `409`，字段校验失败返回 `422`。

### POST /api/v1/sources/rss/test

测试尚未保存的 RSS 地址，请求体只需要 `{"url": "https://example.com/feed.xml"}`。读取失败返回 `422`。

### POST /api/v1/sources/{id}/test

测试已保存的数据源。`/{id}/enable`、`/{id}/disable` 用于启停，`DELETE /api/v1/sources/{id}` 用于删除。

### POST /api/v1/collect 与 GET /api/v1/collect/status

启动一次后台采集并查询状态。启动成功返回 `202`；已有任务运行时返回 `409`。状态包括 `idle`、`running`、`completed` 和 `failed`，并包含 `job_id`、开始时间、结束时间和错误信息。

---

## 内容接口

### GET /api/v1/content

列出内容条目，支持可选过滤条件。使用游标分页。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `date` | string | 否 | 今天 | 日期，格式 YYYY-MM-DD |
| `content_type` | string | 否 | — | 内容类型过滤（text/video/audio/image） |
| `platform` | string | 否 | — | 来源平台过滤 |
| `limit` | int | 否 | 50 | 返回数量（1-200） |
| `cursor` | int | 否 | — | 分页游标（上一页最后一条的 id） |

**响应**：`ContentListResponse`

```json
{
  "items": [
    {
      "id": 42,
      "content_type": "text",
      "title": "OpenAI 发布 GPT-5",
      "source_platform": "rss-hacker-news",
      "source_url": "https://example.com/article",
      "published_at": "2025-01-15T10:30:00Z",
      "summary": "OpenAI 今日发布了...",
      "thumbnail_url": null,
      "media_url": null,
      "duration_sec": null,
      "importance_score": 4.0,
      "tags": ["GPT", "OpenAI", "LLM"],
      "category": "AI",
      "date_partition": "2025-01-15"
    }
  ],
  "meta": {
    "limit": 50,
    "next_cursor": 41
  }
}
```

**分页**：当 `meta.next_cursor` 不为 null 时，将其作为下一次请求的 `cursor` 参数获取下一页。

**缓存**：300 秒

---

### GET /api/v1/content/{id}

根据 ID 获取单个内容条目的完整信息。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | int | 内容条目 ID |

**响应**：`ContentItemDetail`

```json
{
  "id": 42,
  "content_type": "text",
  "title": "OpenAI 发布 GPT-5",
  "source_platform": "rss-hacker-news",
  "source_url": "https://example.com/article",
  "published_at": "2025-01-15T10:30:00Z",
  "summary": "OpenAI 今日发布了...",
  "full_text": "完整的文章正文内容...",
  "thumbnail_url": null,
  "media_url": null,
  "duration_sec": null,
  "image_urls": ["https://example.com/img1.jpg"],
  "importance_score": 4.0,
  "tags": ["GPT", "OpenAI", "LLM"],
  "category": "AI",
  "date_partition": "2025-01-15",
  "raw_metadata": {}
}
```

**错误**：`404` — 内容不存在

**缓存**：1800 秒

---

### GET /api/v1/content/search

基于 pg_trgm 三元组相似度的全文搜索，匹配标题和正文。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `q` | string | 是 | — | 搜索关键词（1-200 字符） |
| `content_type` | string | 否 | — | 内容类型过滤 |
| `limit` | int | 否 | 20 | 返回数量（1-50） |

**响应**：`ContentSearchResponse`

```json
{
  "items": [...],
  "query": "GPT",
  "total": 15
}
```

**缓存**：300 秒

---

### POST /api/v1/content/semantic

语义向量搜索。服务端实时将查询文本转为向量后与内容做余弦相似度匹配。

**前提**：需要配置 `EMBED_MODEL` 和 `EMBED_API_KEY` 环境变量。

**请求体**：

```json
{
  "query": "大语言模型的最新进展",
  "content_type": "text",
  "date_from": "2025-01-01",
  "limit": 10
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 搜索文本（1-500 字符） |
| `content_type` | string | 否 | 内容类型过滤 |
| `date_from` | string | 否 | 起始日期（YYYY-MM-DD） |
| `limit` | int | 否 | 返回数量（1-50，默认 10） |

**响应**：`SemanticSearchResponse`

```json
{
  "items": [...],
  "query": "大语言模型的最新进展"
}
```

**错误**：
- `503` — 语义搜索未启用（未配置 embedder）
- `502` — 向量生成失败

**缓存**：不缓存

---

### GET /api/v1/content/trending

获取指定日期的热门内容，按重要性分数降序排列。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `date` | string | 否 | 今天 | YYYY-MM-DD |
| `content_type` | string | 否 | — | 内容类型过滤 |
| `limit` | int | 否 | 50 | 返回数量（1-200） |

**响应**：`ContentListResponse`

**缓存**：300 秒

---

### GET /api/v1/content/topics/trending

按分类聚合的热门主题统计，包含数量、来源数、平均重要性和热门标签。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `date` | string | 否 | 今天 | 基准日期 |
| `days` | int | 否 | 1 | 统计天数范围（1-7） |
| `limit` | int | 否 | 10 | 返回分类数（1-20） |

**响应**：`TrendingTopicsResponse`

```json
{
  "date": "2025-01-15",
  "topics": [
    {
      "category": "AI",
      "count": 45,
      "sources": 8,
      "avg_importance": 3.2,
      "top_tags": ["GPT", "OpenAI", "LLM", "Anthropic"]
    },
    {
      "category": "开源",
      "count": 23,
      "sources": 5,
      "avg_importance": 2.8,
      "top_tags": ["Linux", "Rust", "Kubernetes"]
    }
  ]
}
```

**缓存**：300 秒

---

### GET /api/v1/content/bundle

获取某个主题分类下的素材包。PostMaker 使用此接口按主题批量获取素材。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `category` | string | 是 | — | 分类名称（AI/云计算/开源/...） |
| `date` | string | 否 | 今天 | YYYY-MM-DD |
| `limit` | int | 否 | 20 | 返回数量（1-100） |

**响应**：`ContentBundleResponse`

```json
{
  "category": "AI",
  "items": [...],
  "total": 15
}
```

**缓存**：300 秒

---

### POST /api/v1/content/{id}/mark_used

标记某素材已被特定人设使用。PostMaker 生成内容后调用此接口进行使用追踪。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | int | 内容条目 ID |

**请求体**：

```json
{
  "persona_id": "tech-reviewer"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `persona_id` | string | 是 | 人设 ID（1-100 字符） |

**响应**：

```json
{
  "ok": true,
  "content_id": 42,
  "persona_id": "tech-reviewer"
}
```

**错误**：`404` — 内容不存在

**缓存**：不缓存

---

## 知识接口

### GET /api/v1/knowledge

列出近期知识条目（跨平台聚合的事件），按重要性排序。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `days` | int | 否 | 7 | 近 N 天（1-90） |
| `category` | string | 否 | — | 分类过滤 |
| `limit` | int | 否 | 50 | 返回数量（1-200） |
| `cursor` | int | 否 | — | 分页游标 |

**响应**：`KnowledgeListResponse`

```json
{
  "items": [
    {
      "id": 10,
      "canonical_title": "OpenAI GPT-5 发布",
      "summary": "跨平台聚合的摘要...",
      "category": "AI",
      "tags": ["GPT", "OpenAI"],
      "importance_score": 4.5,
      "source_count": 3,
      "first_seen_at": "2025-01-15T08:00:00Z",
      "last_seen_at": "2025-01-15T14:00:00Z"
    }
  ],
  "meta": {
    "limit": 50,
    "next_cursor": null
  }
}
```

**缓存**：300 秒

---

### GET /api/v1/knowledge/{id}

获取单个知识条目的详情，包含关联的来源文章列表。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | int | 知识条目 ID |

**响应**：`KnowledgeEntryDetail`

```json
{
  "id": 10,
  "canonical_title": "OpenAI GPT-5 发布",
  "summary": "...",
  "full_text": "...",
  "category": "AI",
  "tags": ["GPT", "OpenAI"],
  "image_urls": [],
  "importance_score": 4.5,
  "source_count": 3,
  "first_seen_at": "2025-01-15T08:00:00Z",
  "last_seen_at": "2025-01-15T14:00:00Z",
  "sources": [
    {
      "id": 42,
      "title": "OpenAI Launches GPT-5",
      "source_platform": "rss-hacker-news",
      "source_url": "https://...",
      "published_at": "2025-01-15T08:00:00Z"
    },
    {
      "id": 55,
      "title": "GPT-5 正式发布",
      "source_platform": "rss-36kr",
      "source_url": "https://...",
      "published_at": "2025-01-15T10:00:00Z"
    }
  ]
}
```

**错误**：`404` — 知识条目不存在

**缓存**：1800 秒

---

### POST /api/v1/knowledge/semantic

对知识条目进行语义搜索。

**前提**：需要配置 `EMBED_MODEL` 和 `EMBED_API_KEY`。

**请求体**：

```json
{
  "query": "人工智能安全",
  "category": "AI",
  "limit": 10
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 搜索文本（1-500 字符） |
| `category` | string | 否 | 分类过滤 |
| `limit` | int | 否 | 返回数量（1-50，默认 10） |

**响应**：`KnowledgeSemanticResponse`

**错误**：`503` — 未配置 embedder / `502` — 向量生成失败

---

## 统计接口

### GET /api/v1/stats/overview

知识库整体统计概览。

**响应**：`StatsOverview`

```json
{
  "total_items": 15234,
  "by_type": {
    "text": 14500,
    "video": 500,
    "audio": 200,
    "image": 34
  },
  "by_platform": {
    "rss-hacker-news": 5000,
    "rss-36kr": 3000,
    "rss-producthunt": 1500
  },
  "latest_date": "2025-01-15"
}
```

**缓存**：600 秒

---

### GET /api/v1/stats/trending

获取指定日期的热门内容排行（与 `/api/v1/content/trending` 功能类似，响应格式不同）。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `date` | string | 否 | 今天 | YYYY-MM-DD |
| `content_type` | string | 否 | — | 内容类型过滤 |
| `limit` | int | 否 | 50 | 返回数量（1-200） |

**响应**：`TrendingResponse`

```json
{
  "date": "2025-01-15",
  "items": [...]
}
```

**缓存**：300 秒

---

## 元接口

### GET /health

就绪探针，检查 PostgreSQL 和 Redis 连接状态。

**响应**：

```json
{
  "status": "ok",
  "postgres": "ok",
  "redis": "ok"
}
```

- `status` 为 `"ok"` 时返回 `200`
- 任一组件不可用时 `status` 为 `"degraded"`，返回 `503`

### GET /

API 根路径，返回基本导航信息。

```json
{
  "name": "DataRadar Knowledge Base API",
  "docs": "/docs",
  "health": "/health"
}
```

---

## 响应模型参考

### ContentItemSummary

列表项的轻量级模型。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 唯一 ID |
| `content_type` | string | text/video/audio/image |
| `title` | string | 标题 |
| `source_platform` | string | 来源平台 |
| `source_url` | string? | 原文 URL |
| `published_at` | datetime? | 发布时间 |
| `summary` | string? | 摘要 |
| `thumbnail_url` | string? | 缩略图 |
| `media_url` | string? | 媒体 URL |
| `duration_sec` | int? | 时长（秒） |
| `importance_score` | float | 重要性评分（1-5） |
| `tags` | string[] | 标签列表 |
| `category` | string? | 分类 |
| `date_partition` | date? | 日期分区 |

### ContentItemDetail

继承 `ContentItemSummary`，额外包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `full_text` | string? | 完整正文 |
| `image_urls` | string[] | 文章图片 URL 列表 |
| `raw_metadata` | object | 原始元数据 |

### KnowledgeEntrySummary

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 唯一 ID |
| `canonical_title` | string | 代表性标题 |
| `summary` | string? | 聚合摘要 |
| `category` | string? | 分类 |
| `tags` | string[] | 标签 |
| `importance_score` | float | 重要性评分 |
| `source_count` | int | 报道平台数量 |
| `first_seen_at` | datetime? | 首次出现时间 |
| `last_seen_at` | datetime? | 最近出现时间 |

### TrendingTopic

| 字段 | 类型 | 说明 |
|------|------|------|
| `category` | string | 分类名称 |
| `count` | int | 内容条目数量 |
| `sources` | int | 来源数量 |
| `avg_importance` | float | 平均重要性 |
| `top_tags` | string[] | 热门标签（最多 10 个） |

---

## 错误处理

所有错误返回标准 JSON 格式：

```json
{
  "detail": "Content item not found."
}
```

| HTTP 状态码 | 说明 |
|------------|------|
| `404` | 资源不存在 |
| `422` | 请求参数验证失败 |
| `502` | 外部服务调用失败（如向量生成） |
| `503` | 功能未启用（如语义搜索未配置） |

---

## 交互式文档

API 服务启动后，可通过以下地址访问自动生成的交互式文档：

- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`
