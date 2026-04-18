# 测试指南

## 测试分层

```
┌─────────────────────────────────────────┐
│  L3  E2E 测试                           │
│  需要真实 AI API + DataRadar API        │
│  验证完整用户场景                        │
├─────────────────────────────────────────┤
│  L2  集成测试                           │
│  Mock 外部依赖，验证模块间协作          │
│  如：全管道 mock LLM + mock HTTP        │
├─────────────────────────────────────────┤
│  L1  单元测试                           │
│  纯逻辑验证，无外部依赖                 │
│  如：匹配引擎、解析器、输出格式         │
└─────────────────────────────────────────┘
```

| 层级 | 范围 | 外部依赖 | 速度 | 数量 |
|------|------|----------|------|------|
| L1 单元 | 单个函数/类 | 无 | 毫秒级 | 多 |
| L2 集成 | 模块间协作 | Mock | 秒级 | 中 |
| L3 E2E | 完整流程 | 真实服务 | 10s+ | 少 |

---

## 运行方式

### PostMaker 测试

```bash
cd PostMaker

# 运行全部测试（不含 E2E）
uv run pytest tests/ -v -m "not e2e"

# 运行特定测试文件
uv run pytest tests/test_persona_matcher.py -v

# 含 E2E（需真实 AI API + DataRadar 运行）
AI_API_KEY="your-key" AI_MODEL="openai/gpt-4o" \
uv run pytest tests/ -v

# 查看覆盖率
uv run pytest tests/ -v -m "not e2e" --cov=postmaker
```

### DataRadar 测试

```bash
cd DataRadar

# 运行全部测试
uv run pytest tests/ -v
```

---

## PostMaker 测试详解（48 个）

### test_config.py — 配置加载

| 测试 | 说明 |
|------|------|
| `test_load_config` | 加载 config.yaml 并验证结构 |
| `test_env_override_api_key` | AI_API_KEY 环境变量覆盖 |
| `test_env_override_model` | AI_MODEL 环境变量覆盖 |
| `test_env_override_postgres` | POSTGRES_DSN 环境变量覆盖 |

### test_models.py — 数据模型

| 测试 | 说明 |
|------|------|
| `test_material_creation` | Material 模型创建 |
| `test_material_defaults` | Material 默认值 |
| `test_persona_creation` | Persona 模型创建 |
| `test_draft_status` | DraftStatus 枚举 |
| `test_generation_task` | GenerationTask 关联 |

### test_persona_loader.py — 人设解析

| 测试 | 说明 |
|------|------|
| `test_load_persona_file` | 解析 YAML frontmatter + Markdown body |
| `test_load_all_personas` | 批量加载 personas 目录 |
| `test_persona_style` | PersonaStyle 字段验证 |
| `test_persona_interests` | PersonaInterests 字段验证 |

### test_persona_matcher.py — 人设匹配

| 测试 | 说明 |
|------|------|
| `test_match_by_topic` | topics 交集匹配 |
| `test_match_importance_filter` | importance 阈值过滤 |
| `test_match_empty_topics` | 空 topics 匹配所有 |
| `test_build_tasks` | 构建生成任务列表 |
| `test_build_tasks_with_existing` | 去重跳过已生成组合 |

### test_prompt_builder.py — Prompt 构建

| 测试 | 说明 |
|------|------|
| `test_build_messages` | 构建 system + user 消息 |
| `test_length_preference_mapping` | short/medium/long 字数映射 |
| `test_summary_vs_fulltext` | ai_summary 优先，不足时回退 full_text |

### test_output.py — 双格式输出

| 测试 | 说明 |
|------|------|
| `test_save_markdown` | Markdown 文件生成 + YAML frontmatter |
| `test_save_html` | HTML 文件生成 + 内联 CSS |
| `test_markdown_frontmatter` | frontmatter 字段完整性 |
| `test_html_template` | HTML 模板渲染 |

### test_dataradar_client.py — API 客户端（L2 集成）

使用 `respx` 库 mock HTTP 请求，验证 DataRadarClient 的所有方法：

| 测试 | 说明 |
|------|------|
| `test_list_content` | 列表获取 |
| `test_list_content_with_date` | 带日期参数 |
| `test_get_content_detail` | 详情获取 |
| `test_search` | 关键词搜索 |
| `test_get_trending` | 热点获取 |
| `test_get_trending_topics` | 分类趋势 |
| `test_get_bundle` | 素材包获取 |
| `test_mark_used` | 标记使用 |
| `test_parse_material_nullable_fields` | 可空字段解析 |
| `test_http_error_404` | HTTP 错误处理 |

### test_generator.py — 内容生成器（L2 集成）

使用 `monkeypatch` mock LLM 调用：

| 测试 | 说明 |
|------|------|
| `test_parse_output_normal` | 正常输出解析 |
| `test_parse_output_strips_heading` | 去除 # 标题前缀 |
| `test_parse_output_single_line` | 单行输出处理 |
| `test_generate_batch_concurrency` | 并发生成（Semaphore） |
| `test_generate_batch_handles_exception` | 异常处理（不中断其他任务） |
| `test_generate_one_success` | 单任务完整流程 |
| `test_generate_one_empty_response` | 空响应处理 |
| `test_model_routing_high_importance` | importance≥4 路由到 high 模型 |
| `test_generate_with_refine` | 二阶段优化流程 |

### test_pipeline_integration.py — 全管道集成（L2）

Mock DataRadar HTTP + LLM，验证端到端管道：

| 测试 | 说明 |
|------|------|
| `test_full_pipeline_trending` | 完整热门素材管道（3 素材 → 4 任务 → 4 输出） |
| `test_full_pipeline_with_dedup` | 去重过滤已生成组合 |
| `test_full_pipeline_dry_run` | dry-run 模式不生成 |
| `test_full_pipeline_single_persona` | 指定单人设 |
| `test_full_pipeline_topic_bundle` | 按主题获取素材包 |

### test_e2e.py — E2E（L3）

需要真实 AI API 和 DataRadar 服务运行：

| 测试 | 前提 | 说明 |
|------|------|------|
| `test_e2e_fetch_materials` | DataRadar API | 从真实 API 获取素材 |
| `test_e2e_generate_from_trending` | AI API + DataRadar | 完整生成流程 |

---

## Mock 策略

### HTTP Mock（respx）

用于 mock DataRadarClient 的 HTTP 请求：

```python
import respx
from httpx import Response

@respx.mock
async def test_list_content(mock_materials):
    respx.get("http://localhost:8000/api/v1/content").mock(
        return_value=Response(200, json={
            "items": [MOCK_CONTENT_ITEM_AI],
            "meta": {"limit": 50, "next_cursor": None}
        })
    )
    async with DataRadarClient("http://localhost:8000") as client:
        materials = await client.list_content()
    assert len(materials) == 1
```

### LLM Mock（monkeypatch）

用于 mock AIClient.chat() 的 LLM 调用：

```python
async def test_generate_one(monkeypatch):
    async def mock_chat(messages, **kwargs):
        return "# 测试标题\n\n这是正文内容..."

    monkeypatch.setattr(generator.ai_client, "chat", mock_chat)
    draft = await generator._generate_one(task)
    assert draft.title == "测试标题"
```

### Fixture 设计（conftest.py）

共享测试数据定义在 `tests/conftest.py`：

- `MOCK_CONTENT_ITEM_AI` — AI 类素材 JSON（importance=4）
- `MOCK_CONTENT_ITEM_OPENSOURCE` — 开源类素材 JSON（importance=3）
- `MOCK_CONTENT_ITEM_BIZ` — 商业类素材 JSON（importance=2）
- `mock_materials` fixture — 3 个 Material 对象
- `mock_personas` fixture — 2 个 Persona 对象（tech-reviewer + code-craftsman）

---

## E2E 测试前提

运行 E2E 测试需要：

1. **DataRadar API 运行中**（`http://localhost:8000`）
2. **PostgreSQL + Redis 运行中**（Docker）
3. **AI API 密钥**（通过环境变量传入）

```bash
# 启动基础设施
cd DataRadar/docker && docker compose up postgres redis -d

# 启动 API
cd DataRadar
POSTGRES_DSN="postgresql://dataradar:dataradar_secret@localhost:5432/knowledge_base" \
REDIS_URL="redis://localhost:6379/0" \
uv run uvicorn api_server.main:app --port 8000 &

# 运行 E2E
cd PostMaker
AI_API_KEY="your-key" AI_MODEL="openai/gpt-4o" \
uv run pytest tests/test_e2e.py -v
```

E2E 测试使用 `@pytest.mark.e2e` 标记，默认被 `-m "not e2e"` 排除。在没有 `AI_API_KEY` 环境变量时自动跳过。

---

## DataRadar 测试

DataRadar 测试覆盖：

| 文件 | 说明 |
|------|------|
| `test_config_loader.py` | 配置加载验证 |
| `test_date_parser.py` | 自然语言日期解析 |
| `test_url_utils.py` | URL 工具函数 |
| `test_title_similarity.py` | 标题相似度算法 |

---

## 添加新测试

### PostMaker 测试约定

1. 测试文件放在 `PostMaker/tests/` 目录下，文件名 `test_*.py`
2. 使用 `pytest-asyncio` 处理异步测试，标记 `@pytest.mark.asyncio`
3. HTTP mock 使用 `respx`，LLM mock 使用 `monkeypatch`
4. 共享 fixture 定义在 `conftest.py`
5. E2E 测试标记 `@pytest.mark.e2e`

### pytest 配置

`pyproject.toml` 中的 pytest 配置：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "e2e: end-to-end tests requiring real AI API and DataRadar",
]
```
