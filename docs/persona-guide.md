# 人设创建指南

## 概述

PostMaker 使用人设（Persona）系统实现内容差异化。每个人设定义了独立的写作风格、关注领域和匹配规则，同一素材经过不同人设生成的内容在语气、深度和侧重点上各不相同。

人设文件存放在 `PostMaker/config/personas/` 目录下，采用 **YAML frontmatter + Markdown body** 格式。

---

## 文件格式

```yaml
---
id: "persona-id"           # 唯一标识（英文，用于文件名和去重）
name: "人设名称"            # 显示名称
description: "一句话描述"    # 简要说明
style:
  tone: "professional_analytical"    # 写作语气
  language: "zh-CN"                  # 输出语言
  length_preference: "long"          # 篇幅偏好
interests:
  topics: ["AI", "云计算"]           # 关注主题
  min_importance: 3                  # 最低重要性阈值
---

这里是 Markdown 正文，作为 LLM 的 system prompt。
可以包含标题、列表、分节等任意 Markdown 格式。
```

### frontmatter 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识，建议英文短横线格式（如 `tech-reviewer`） |
| `name` | string | 是 | 人设显示名称 |
| `description` | string | 否 | 简要描述，用于 `postmaker personas` 命令输出 |
| `style.tone` | string | 是 | 写作语气风格 |
| `style.language` | string | 是 | 输出语言代码 |
| `style.length_preference` | string | 是 | 篇幅偏好：`short` / `medium` / `long` |
| `interests.topics` | list | 否 | 关注主题列表（空列表匹配所有素材） |
| `interests.min_importance` | int | 否 | 最低重要性阈值，默认 1 |

### style.tone 参考值

| 值 | 说明 | 适用场景 |
|----|------|----------|
| `professional_analytical` | 专业分析型，严谨有深度 | 科技评论、行业分析 |
| `casual_technical` | 轻松技术型，像同事聊天 | 技术分享、工具推荐 |
| `enthusiastic` | 热情洋溢型 | 产品推荐、新鲜事物 |
| `educational` | 教学型，循序渐进 | 教程、入门指南 |
| `news_brief` | 新闻简报型，简洁客观 | 快讯、日报 |

tone 的值本身不影响匹配逻辑，但会注入 prompt 中影响 LLM 的输出风格。你可以使用任意字符串。

### style.length_preference 映射

| 值 | 目标字数 | 适用场景 |
|----|----------|----------|
| `short` | 800 - 1,200 字 | 快讯、简评 |
| `medium` | 1,500 - 2,500 字 | 技术分享、工具评测 |
| `long` | 3,000 - 5,000 字 | 深度分析、长文评论 |

### Markdown body

frontmatter 下方的 Markdown 内容作为 LLM 的 **system prompt**，是人设最核心的部分。它直接决定了 LLM 的写作风格和内容质量。

建议包含：
- **角色设定**：你是谁、有什么背景
- **写作风格**：具体的写作规则和偏好
- **内容重点**：关注的分析角度
- **禁忌**：需要避免的内容或表述

---

## 匹配规则

当一篇素材到达 PostMaker，系统会将它与所有人设进行匹配，决定哪些人设应该为这篇素材生成内容。

### 匹配算法

```
对每个人设 persona：
  1. 检查 importance：material.importance_score >= persona.interests.min_importance
     → 不满足则跳过

  2. 检查 topics：
     → 如果 persona.interests.topics 为空列表 → 匹配所有素材
     → 否则：取 persona.topics 与 material.(tags + category) 的交集
       → 交集非空 → 匹配成功
       → 交集为空 → 跳过
```

### 匹配示例

假设素材：`importance_score=4, tags=["GPT", "OpenAI"], category="AI"`

| 人设 | min_importance | topics | 匹配结果 |
|------|---------------|--------|---------|
| 科技评论家 | 3 | ["AI", "云计算"] | 匹配（4≥3 且 "AI" 交集非空） |
| 代码匠人 | 2 | ["开源", "开发工具", "AI"] | 匹配（4≥2 且 "AI" 交集非空） |
| 新闻编辑 | 1 | [] | 匹配（4≥1 且 topics 为空匹配所有） |
| 安全专家 | 3 | ["网络安全"] | 不匹配（topics 交集为空） |
| 深度分析师 | 5 | ["AI"] | 不匹配（4 < 5） |

### topics 匹配细节

- 匹配不区分大小写（`"ai"` 和 `"AI"` 等价）
- 素材的 topics 来源：`material.tags`（AI 提取标签数组）+ `material.category`（AI 分类）
- DataRadar 的 AI 分类为以下 8 类之一：AI / 云计算 / 开源 / 网络安全 / 商业 / 硬件 / 开发工具 / 其他

### 去重

同一 `(material_id, persona_id)` 组合只会生成一次。去重来源：
- 内存：`build_generation_tasks()` 的 `existing_pairs` 参数
- 数据库：`postmaker.drafts` 表的 `UNIQUE (material_id, persona_id)` 约束

---

## 示例：创建新人设

### 1. 创建文件

在 `PostMaker/config/personas/` 下创建 YAML 文件：

```yaml
# config/personas/security-analyst.yaml
---
id: "security-analyst"
name: "安全分析师"
description: "网络安全领域专家，关注漏洞和威胁情报"
style:
  tone: "professional_analytical"
  language: "zh-CN"
  length_preference: "medium"
interests:
  topics: ["网络安全", "AI"]
  min_importance: 2
---

你是一位资深网络安全分析师，拥有 CISSP 和 OSCP 认证。

## 写作风格
- 严谨客观，注重事实和数据
- 技术细节精确，给出 CVE 编号和影响范围
- 为读者提供可执行的防护建议

## 分析框架
- 漏洞影响范围：受影响的系统和版本
- 攻击复杂度：利用难度和前提条件
- 缓解措施：临时和永久修复方案

## 禁忌
- 不提供攻击细节或 PoC 代码
- 不使用制造恐慌的措辞
```

### 2. 验证

```bash
# 查看所有已加载人设
uv run postmaker personas

# 预览匹配结果（不实际生成）
uv run postmaker generate --trending --dry-run
```

### 3. 生成内容

```bash
# 仅用新人设生成
uv run postmaker generate --trending --persona security-analyst --limit 3
```

---

## 最佳实践

### system prompt 编写

1. **具体优于泛泛**：不要写"请写一篇好文章"，而是写"开篇直击核心观点，第二段给出数据支撑"
2. **给出分析框架**：提供具体的思考维度（如"技术创新度 → 行业影响 → 用户价值"）
3. **明确禁忌**：告诉 LLM 什么不能做比告诉它什么能做更有效
4. **控制篇幅**：`length_preference` 只是建议，system prompt 中可以进一步约束

### topics 配置

1. **宁窄勿宽**：topics 太多会导致低相关素材也被匹配
2. **重要性阈值**：高质量人设可以设高 `min_importance`（3-4），只处理重要素材
3. **通用人设**：留一个 `topics: []` 的通用人设作为兜底，确保所有素材都有输出
4. **与 DataRadar 分类对齐**：topics 应使用 DataRadar 的分类名称（AI、云计算、开源、网络安全、商业、硬件、开发工具、其他）以获得最佳匹配

### 差异化策略

矩阵运营的核心是**同一素材，不同角度**：

| 人设 | 角度 | 篇幅 | 目标读者 |
|------|------|------|----------|
| 科技评论家 | 行业趋势分析 | 长文 | 决策者、管理层 |
| 代码匠人 | 技术实操细节 | 中等 | 开发者 |
| 新闻编辑 | 客观事实报道 | 短文 | 快速阅读者 |
| 安全分析师 | 安全影响评估 | 中等 | 安全从业者 |
