# PostMaker

**矩阵运营内容生成系统** — 从 DataRadar 获取素材，通过多人设匹配和 LLM 生成差异化原创内容，输出 Markdown + HTML 双格式。

```
DataRadar API ──→ 素材获取 ──→ 人设匹配 ──→ LLM 生成 ──→ .md + .html
                                  │
                          ┌───────┼───────┐
                     科技评论家  代码匠人   ...
                     深度长文    实操分享
```

## 功能特性

- **多人设系统**：YAML frontmatter + Markdown body 定义人设，支持自定义写作风格和领域兴趣
- **智能匹配**：根据素材分类、标签和重要性自动匹配合适的人设
- **两阶段生成**：Composer（必选）+ Refiner（可选），分级模型路由
- **双格式输出**：Markdown（含 YAML frontmatter）+ HTML（内联 CSS，可直接预览）
- **生成去重**：同一素材 + 人设组合不重复生成
- **DataRadar 集成**：通过 REST API 获取素材，支持热门、搜索、主题包等多种获取方式

## 快速开始

### 安装

```bash
cd PostMaker
uv sync --all-extras
```

### 配置

编辑 `config/config.yaml` 或通过环境变量：

```bash
export AI_API_KEY="your-api-key"
export AI_MODEL="openai/gpt-4o"        # 或 deepseek/deepseek-chat 等
export AI_API_BASE=""                   # 可选，自定义 API 端点
```

确保 DataRadar API 已在 `http://localhost:8000` 运行。

也可以通过环境变量覆盖 DataRadar 地址：

```bash
export DATARADAR_API_BASE="http://127.0.0.1:18000"
export DATARADAR_TIMEOUT=15
```

### 生成内容

```bash
# 从热门素材生成
uv run postmaker generate --trending --limit 5

# 指定主题
uv run postmaker generate --topic AI --limit 3

# 指定人设 + dry-run 预览
uv run postmaker generate --trending --persona tech-reviewer --dry-run

# 启用二阶段优化
uv run postmaker generate --trending --limit 2 --refine
```

## CLI 命令

```bash
# ── 内容生成 ──
postmaker generate [选项]
  --persona <id>          指定人设
  --topic <分类>          按主题获取素材
  --material-id <id>      指定单条素材
  --trending              使用热门素材
  --limit N               素材数量（默认 10）
  --dry-run               预览匹配，不生成
  --refine                启用二阶段优化

# ── 查看人设 ──
postmaker personas

# ── 查看素材 ──
postmaker materials [--search Q] [--trending] [--detail ID]

# ── 生成历史 ──
postmaker history [--persona X]

# ── 配置 ──
postmaker config [section]
```

## 本地内容审核工作台（MVP）

MVP 工作台把素材发现、persona 生成、人工编辑、审核状态、修订历史和 Markdown 导出放在一个本地页面中。草稿默认保存在 `output/workbench.sqlite3`，不要求配置 PostgreSQL；素材仍从 DataRadar API 获取。

```bash
# 确保 DataRadar API 已启动后执行
uv run postmaker workbench
```

打开 <http://127.0.0.1:8787>。如果使用其他端口，可运行 `uv run postmaker workbench --port 9000`。也可以用 `POSTMAKER_WORKBENCH_DB=/path/to/workbench.sqlite3` 指定本地草稿数据库位置。

当前 MVP 的状态流转是「待审核 → 已批准 / 已归档」，每次保存都会创建修订记录。批准后的草稿可从详情页导出 Markdown。工作台不会自动发布到任何平台。

## 人设系统

人设文件放在 `config/personas/` 目录下，YAML frontmatter + Markdown body 格式：

```yaml
---
id: "tech-reviewer"
name: "科技评论家"
description: "资深科技媒体人"
style:
  tone: "professional_analytical"
  language: "zh-CN"
  length_preference: "long"       # short(800-1200) / medium(1500-2500) / long(3000-5000)
interests:
  topics: ["AI", "云计算", "开源"]
  min_importance: 3               # 只匹配重要性 >= 3 的素材
---

你是一位资深科技评论家...
（Markdown body 作为 LLM system prompt）
```

详细指南：[docs/persona-guide.md](../docs/persona-guide.md)

## 输出格式

输出目录结构：`output/{日期}/{人设ID}/{标题}.md|html`

**Markdown**：含 YAML frontmatter（title、persona、source、generated_at、model）

**HTML**：内联 CSS 排版，可直接浏览器预览，包含人设和来源信息

## 配置说明

`config/config.yaml`：

```yaml
app:
  timezone: "Asia/Shanghai"

dataradar:
  api_base: "http://localhost:8000"   # DataRadar API 地址
  timeout: 15

ai:
  model: ""              # 环境变量 AI_MODEL
  api_key: ""            # 环境变量 AI_API_KEY
  api_base: ""           # 环境变量 AI_API_BASE
  temperature: 0.7
  max_tokens: 8000
  refine_enabled: false  # 全局启用 refiner
  models:
    high: ""             # importance >= 4 用此模型
    medium: ""           # 其余用此模型（空则用默认 model）

database:
  postgres_dsn: ""       # 环境变量 POSTGRES_DSN（可选，用于去重和历史记录）

output:
  base_dir: "output"
  formats: ["markdown", "html"]
```

## 测试

```bash
# 运行全部测试（不含 E2E）
uv run pytest tests/ -v -m "not e2e"

# 含 E2E（需真实 AI API + DataRadar 运行）
AI_API_KEY=... AI_MODEL=... uv run pytest tests/ -v
```

当前测试覆盖：57 个通过、2 个 E2E 测试按标记排除，详见 [docs/testing.md](../docs/testing.md)
