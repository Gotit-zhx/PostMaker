# 矩阵运营与 PostMaker 设计思考

---

## 一、矩阵运营是什么

### 1.1 定义

矩阵运营是一种**多平台 × 多账号 × 差异化内容**的规模化内容分发策略。核心思想是：围绕同一个信息源或知识体系，通过多个平台上的多个账号，以不同的人设、语气、内容切角触达不同圈层的受众，形成覆盖面和影响力的指数级放大。

它不是简单的"一稿多发"，而是一套**内容生产 → 风格化改写 → 分平台适配 → 定时分发 → 数据回收**的闭环系统。

### 1.2 矩阵运营的核心要素

```
                     ┌──────────────────────────────────────────────┐
                     │              内 容 中 台                      │
                     │  （知识库 / 素材库 / 热点追踪）                │
                     └────────────────┬─────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                  ▼
             ┌──────────┐     ┌──────────┐       ┌──────────┐
             │ 人设 A    │     │ 人设 B    │       │ 人设 C    │
             │ 科技评论家 │     │ 行业观察者 │       │ 技术极客   │
             │ 深度长文   │     │ 简洁快讯   │       │ 代码实战   │
             └────┬─────┘     └────┬─────┘       └────┬─────┘
                  │                │                   │
          ┌───┬───┤          ┌───┬─┤              ┌───┬┤
          ▼   ▼   ▼          ▼   ▼ ▼              ▼   ▼▼
         微信 知乎 头条     Twitter 即刻 小红书    GitHub 掘金 B站
```

**四个关键维度**：

| 维度 | 说明 | 举例 |
|------|------|------|
| **平台** | 每个平台有不同的内容格式、推荐算法、用户画像 | 微信公众号（长文深度）、Twitter/X（短快信息密度）、小红书（视觉化+标题党）、知乎（问答+专业度） |
| **账号/人设** | 同一平台可以有多个账号，每个账号有清晰的定位 | "AI前沿观察"（行业动态）、"代码匠人"（技术实践）、"数据玩家"（数据分析视角） |
| **内容风格** | 同一条素材，不同人设产出完全不同的内容 | 同一个GPT-5新闻 → 评论家写深度分析、观察者写行业影响、极客写技术拆解 |
| **分发策略** | 发布时间、频率、互动策略因平台和账号而异 | 微信早晨8点、Twitter实时、知乎下午回答问题 |

### 1.3 矩阵运营的价值

1. **风险分散**：单一账号封禁不影响整体触达能力
2. **覆盖面扩大**：不同平台的用户群体有差异，矩阵覆盖更广
3. **内容复用**：一份素材经过改写可以产出 N 份差异化内容，边际成本趋近于零
4. **SEO/算法博弈**：多个账号在同一平台互相引用、评论，提升推荐权重
5. **数据闭环**：不同风格的内容在不同平台的表现数据，反过来优化内容策略

### 1.4 矩阵运营的难点

| 难点 | 传统方案 | 自动化方案的机会 |
|------|---------|----------------|
| 内容差异化 | 人工改写，效率低 | LLM 基于人设 Prompt 自动风格化改写 |
| 多平台适配 | 手动调整格式、图片尺寸 | 平台适配器自动转换（Markdown → 各平台格式） |
| 发布协调 | 人工记时间、切账号 | 定时任务 + 平台 API / RPA 自动发布 |
| 数据回收 | 各平台手动看数据 | 统一数据面板，自动采集阅读/互动/转发数据 |
| 账号安全 | 操作太频繁被风控 | 人性化延迟、IP 隔离、行为模拟 |

---

## 二、DataRadar 在矩阵运营体系中的定位与改进

### 2.1 DataRadar 的现有价值

DataRadar 目前是一个**纯采集 + 知识库系统**，在矩阵运营中扮演的角色是**上游内容中台**——负责"知道世界上发生了什么"。

```
  DataRadar（已有）                PostMaker（待建）
 ┌─────────────────┐           ┌─────────────────────────┐
 │  RSS 采集        │           │  内容生成引擎             │
 │  网页采集        │    ──→    │  人设管理                 │
 │  全文提取        │    ──→    │  平台适配                 │
 │  AI 摘要         │    ──→    │  定时分发                 │
 │  知识库          │    ──→    │  数据回收                 │
 └─────────────────┘           └─────────────────────────┘
    信息采集层                      内容生产 + 分发层
```

**DataRadar 已经能做的事**：
- 从 15+ RSS 源持续追踪行业动态
- 全文提取保留原始素材
- AI 摘要提供快速理解
- 知识库支持语义检索，可按主题查找相关素材
- 跨平台去重避免重复覆盖同一新闻

### 2.2 DataRadar 面向矩阵运营的改进方向

以下改进不是"DataRadar 本身的不足"，而是为了更好地服务下游 PostMaker 而需要增强的能力：

#### 改进 A：内容标签与分类增强

**现状**：`content_items` 表有 `tags` 和 `category` 字段，但目前标签来源单一（RSS 自带或 ETL 简单提取），缺乏系统性的内容分类。

**建议**：在 AI 摘要阶段增加**主题分类**和**关键词提取**，为下游的"哪个人设应该写这条内容"提供决策依据。

```
当前流程：  原文 → AI摘要（200 token 概述）
改进流程：  原文 → AI摘要 + 主题分类 + 关键实体提取 + 热度评估
```

具体做法：修改 `summarize_prompt.txt`，在摘要 Prompt 中增加结构化输出要求：
```
请为以下文章生成：
1. 一段 200 字以内的摘要
2. 主题分类（从以下选择：AI/云计算/开源/网络安全/商业/硬件/开发工具/其他）
3. 3-5 个关键词
4. 热度评估（1-5分，基于话题新颖度和潜在关注度）
以 JSON 格式输出。
```

**影响范围**：`dataradar/ai/summarizer.py` 修改输出解析逻辑，`knowledge_base/repository.py` 的 UPSERT 中写入 tags/category。

#### 改进 B：内容新鲜度与趋势追踪

**现状**：知识库有 `importance_score` 和 `source_count`，但缺少时间维度的趋势分析——一个话题在过去 24 小时被多少不同来源报道，趋势是上升还是下降。

**建议**：新增趋势评分逻辑，PostMaker 可以据此判断"现在应该追这个热点"。

```python
# 趋势评分 = 近24h报道数 × 来源多样性系数 × 时效衰减因子
trend_score = source_count_24h * diversity_factor * recency_decay
```

#### 改进 C：素材输出 API 增强

**现状**：FastAPI 的 `/api/v1/content` 已支持列表、搜索、语义搜索。但缺少面向内容生成场景的接口：

- **按主题聚合**：`GET /api/v1/topics/trending` — 返回当前热门主题及其下的多条素材
- **素材包**：`GET /api/v1/content/bundle?topic=AI&limit=5` — 返回某主题的一组素材（标题+摘要+原文片段），直接可以作为 PostMaker 的输入
- **去重标记**：`POST /api/v1/content/{id}/mark_used` — 标记某条素材已被某人设使用过，避免不同人设写同一个新闻

#### 改进 D：实时采集触发

**现状**：采集是定时批量的（每 N 分钟跑一次）。

**建议**：增加 Webhook / 事件触发机制。当新的高热度内容入库时，主动通知 PostMaker "有新素材可以处理"，缩短从热点出现到内容发布的延迟。

```
DataRadar 采集 → 发现高热度内容 → WebSocket/Webhook → PostMaker 立即启动生成
```

---

## 三、PostMaker 设计思路

### 3.1 系统定位

PostMaker 是矩阵运营的**下半场**——从 DataRadar 提供的结构化素材出发，完成**内容生成 → 风格化 → 平台适配 → 发布 → 数据回收**的全链路。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PostMaker 系统全景                                │
│                                                                             │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐          │
│  │ 素材中心   │ →  │ 创作引擎   │ →  │ 发布引擎   │ →  │ 数据中心   │          │
│  │           │    │           │    │           │    │           │          │
│  │ DataRadar │    │ 人设系统   │    │ 平台适配   │    │ 阅读/互动   │          │
│  │ 知识库API │    │ LLM 改写   │    │ 账号管理   │    │ 趋势分析   │          │
│  │ 手动输入   │    │ 审核队列   │    │ 定时调度   │    │ 策略优化   │          │
│  └───────────┘    └───────────┘    └───────────┘    └───────────┘          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     配置与管理层                                      │    │
│  │  人设配置  │  平台凭证  │  发布规则  │  内容策略  │  安全与风控       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块设计

#### 模块 1：人设系统（Persona Engine）

这是矩阵运营区别于普通自动化发布的**核心差异点**。每个人设是一组约束条件，控制 LLM 如何将素材转化为特定风格的内容。

**人设配置结构**：

```yaml
personas:
  - id: "tech-reviewer"
    name: "科技评论家"
    description: "资深科技媒体人，擅长深度分析，观点犀利"
    
    # 写作风格控制
    style:
      tone: "professional_analytical"     # 专业分析型
      language: "zh-CN"
      length_preference: "long"           # 长文偏好
      vocabulary_level: "advanced"        # 专业术语多
      emoji_usage: "minimal"             # 少用表情
      
    # System Prompt（注入 LLM）
    system_prompt: |
      你是一位资深科技评论家，拥有 15 年行业经验。
      你的文风特点：
      - 开篇直击核心观点，不写空话
      - 善于用类比让复杂技术概念通俗化
      - 每篇文章有明确的"观点主张"，而非中立报道
      - 结尾留一个开放性思考题，引发讨论
      - 偶尔用反问句制造张力
      你绝不使用的表达：「震惊！」「重磅！」「不转不是中国人」
      
    # 内容偏好（决定这个人设对哪些素材感兴趣）
    interests:
      topics: ["AI", "云计算", "开源"]
      min_importance: 3                   # 只关注重要度 >= 3 的内容
      
    # 绑定的平台账号
    accounts:
      - platform: "wechat"
        account_id: "tech_review_2024"
      - platform: "zhihu"
        account_id: "TechReviewer"
        
  - id: "code-craftsman"
    name: "代码匠人"
    style:
      tone: "casual_technical"
      length_preference: "medium"
      code_block_usage: "heavy"           # 大量代码示例
    system_prompt: |
      你是一个爱折腾的全栈工程师，喜欢用最少的代码解决问题。
      文风特点：
      - 开头先甩一段代码或命令行
      - "Talk is cheap, show me the code" 是你的信条
      - 用"踩坑"和"填坑"的叙事结构
      - 标题常用「xxx 的 N 种姿势」「一行代码搞定 xxx」格式
    interests:
      topics: ["开源", "开发工具", "AI"]
    accounts:
      - platform: "juejin"
        account_id: "code_craftsman"
      - platform: "github"
        account_id: "codecraftsman"
```

**人设匹配逻辑**：

```
新素材入库 → 遍历人设的 interests 配置 → 匹配的人设进入创作队列
                                          ↓
                                  人设 A 匹配 → 用人设 A 的 Prompt 生成内容
                                  人设 B 匹配 → 用人设 B 的 Prompt 生成内容
                                  人设 C 不匹配 → 跳过
```

#### 模块 2：创作引擎（Content Engine）

将素材 + 人设 + 平台约束输入 LLM，产出适合发布的内容。

**创作流程**：

```
┌─────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌────────┐
│ 素材选择  │ →  │ 人设注入  │ →  │ 平台约束注入  │ →  │ LLM 生成  │ →  │ 审核队列 │
└─────────┘    └──────────┘    └─────────────┘    └──────────┘    └────────┘
```

**平台约束示例**：

```yaml
platforms:
  wechat:
    name: "微信公众号"
    constraints:
      max_title_length: 64
      max_body_length: 20000
      supports_markdown: false          # 需要转换为富文本
      supports_images: true
      image_requirements:
        cover: { width: 900, height: 383, required: true }
        max_inline: 20
      best_publish_times: ["07:30", "12:00", "21:00"]
      
  twitter:
    name: "Twitter/X"
    constraints:
      max_body_length: 280              # 单条限制
      supports_thread: true             # 支持线程
      thread_max_tweets: 10
      supports_images: true
      image_requirements:
        max_per_tweet: 4
        aspect_ratio: "16:9"
      best_publish_times: ["09:00", "13:00", "19:00"]
      
  zhihu:
    name: "知乎"
    constraints:
      max_title_length: 100
      max_body_length: 50000
      supports_markdown: true
      content_types: ["article", "answer"]  # 文章或回答
      best_publish_times: ["10:00", "14:00", "20:00"]
      
  xiaohongshu:
    name: "小红书"
    constraints:
      max_title_length: 20
      max_body_length: 1000
      supports_markdown: false
      emoji_density: "high"             # 平台文化：大量 emoji
      hashtag_required: true
      image_requirements:
        min_images: 1
        aspect_ratio: "3:4"
      best_publish_times: ["12:00", "18:00", "21:00"]
```

**Prompt 组装逻辑**（伪代码）：

```python
def build_generation_prompt(material, persona, platform):
    return f"""
{persona.system_prompt}

## 你要发布的平台
{platform.name}，字数限制 {platform.constraints.max_body_length}，
{'支持 Markdown' if platform.constraints.supports_markdown else '纯文本格式'}。

## 原始素材
标题：{material.title}
来源：{material.source}
摘要：{material.ai_summary}
原文要点：{material.full_text[:3000]}

## 任务
基于以上素材，以你的人设风格撰写一篇适合在 {platform.name} 发布的内容。
{'包含 3-5 个相关话题标签。' if platform.constraints.hashtag_required else ''}
{'将内容拆分为多条推文（线程），每条不超过 280 字。' if platform.name == 'Twitter/X' else ''}
"""
```

#### 模块 3：发布引擎（Publisher Engine）

负责将生成的内容投递到各平台。这是技术实现中**最脏最复杂**的部分，因为各平台 API 标准不一、封控策略不同。

**发布策略的两条路线**：

| 方式 | 优点 | 缺点 | 适用平台 |
|------|------|------|---------|
| **官方 API** | 稳定、合规、无风控风险 | 很多平台没有发布 API 或限制严格 | Twitter、GitHub、Medium、WordPress |
| **RPA 模拟** | 覆盖所有平台 | 需要维护浏览器自动化、容易被风控 | 微信公众号、知乎、小红书、即刻 |

**建议的混合架构**：

```python
class PublisherRegistry:
    """发布器注册中心，每个平台一个 Publisher 实现。"""
    
    publishers = {
        "twitter": TwitterAPIPublisher,       # 官方 API
        "github": GitHubAPIPublisher,         # 官方 API
        "medium": MediumAPIPublisher,         # 官方 API
        "wechat": WechatRPAPublisher,         # Playwright RPA
        "zhihu": ZhihuRPAPublisher,           # Playwright RPA
        "xiaohongshu": XiaohongshuRPAPublisher,  # Playwright RPA
        "juejin": JuejinRPAPublisher,         # Playwright RPA
    }
```

**风控策略**：

```yaml
safety:
  # 全局发布间隔
  min_interval_between_posts: 300       # 同账号至少间隔 5 分钟
  max_posts_per_day_per_account: 5      # 单账号每日上限
  
  # 行为模拟
  human_like_delay:
    typing_speed: [50, 120]             # 模拟打字速度（字符/秒）
    click_delay: [0.3, 1.5]             # 点击间隔（秒）
    scroll_before_post: true            # 发布前随机滚动页面
    
  # IP 隔离
  proxy_pool:
    enabled: true
    rotate_per_account: true            # 每个账号绑定固定 IP
```

#### 模块 4：数据回收（Analytics Engine）

闭环的关键——追踪每条内容在各平台的表现，反馈到内容策略。

**采集的数据维度**：

```python
class PostMetrics:
    post_id: str
    platform: str
    account_id: str
    persona_id: str
    material_id: str          # 对应 DataRadar 的 content_item id
    
    # 基础数据
    views: int
    likes: int
    comments: int
    shares: int
    bookmarks: int
    
    # 衍生指标
    engagement_rate: float    # (likes + comments + shares) / views
    
    # 时间维度
    published_at: datetime
    metrics_updated_at: datetime
    hour_1_views: int         # 发布后 1 小时阅读量（衡量推荐强度）
```

**数据驱动的策略优化**：

```
人设 A 在知乎的 AI 主题文章 engagement_rate = 8.2%
人设 A 在知乎的开源主题文章 engagement_rate = 2.1%
→ 结论：人设 A 在知乎应聚焦 AI 主题

人设 B 在小红书 21:00 发布 engagement_rate = 6.5%
人设 B 在小红书 12:00 发布 engagement_rate = 3.8%
→ 结论：人设 B 在小红书应优先 21:00 发布
```

### 3.3 整体数据模型

```
┌──────────────────────────────────────────────────────────────────┐
│                         PostMaker 数据模型                       │
│                                                                  │
│  ┌─────────┐   N:N    ┌──────────┐   1:N    ┌───────────┐      │
│  │ Material │ ←────→  │ Persona  │ ←────→  │  Account   │      │
│  │ (素材)   │          │ (人设)    │          │  (账号)    │      │
│  └────┬────┘          └────┬─────┘          └─────┬─────┘      │
│       │                    │                       │             │
│       │ 1:N                │ 1:N                   │ 1:N         │
│       ▼                    ▼                       ▼             │
│  ┌─────────┐          ┌──────────┐          ┌───────────┐      │
│  │ Draft   │ ←────→  │ Content  │ ←────→  │   Post     │      │
│  │ (草稿)   │   1:1    │ (成稿)   │   1:1    │  (已发布)   │      │
│  └─────────┘          └────┬─────┘          └─────┬─────┘      │
│                            │                       │             │
│                            │                       │ 1:N         │
│                            │                       ▼             │
│                            │               ┌───────────┐        │
│                            │               │  Metrics   │        │
│                            │               │  (数据)    │        │
│                            │               └───────────┘        │
│                            │                                     │
│                     ┌──────┴──────┐                              │
│                     │  Platform   │                              │
│                     │  (平台配置)  │                              │
│                     └─────────────┘                              │
└──────────────────────────────────────────────────────────────────┘
```

**关键实体说明**：

| 实体 | 说明 | 关键字段 |
|------|------|---------|
| Material | 素材，来自 DataRadar 或手动输入 | source_id, title, summary, full_text, topics, importance |
| Persona | 人设配置 | id, name, system_prompt, style, interests |
| Account | 平台账号 | platform, credentials, proxy_config, rate_limits |
| Draft | LLM 生成的初稿 | material_id, persona_id, platform, raw_content |
| Content | 审核通过的成稿 | draft_id, final_content, media_urls, status |
| Post | 已发布记录 | content_id, account_id, published_at, platform_post_id |
| Metrics | 发布后的数据 | post_id, views, likes, comments, engagement_rate |
| Platform | 平台规则配置 | name, constraints, api_type, best_times |

### 3.4 工作流设计

**完整的自动化工作流**：

```
阶段 0：素材入库（DataRadar 驱动）
  ├── DataRadar 定时采集 → 新素材写入知识库
  ├── Webhook 通知 PostMaker "有新素材"
  └── 或 PostMaker 定时拉取 DataRadar API

阶段 1：素材筛选与分配
  ├── 按 importance_score + 趋势评分 筛选值得创作的素材
  ├── 按 topics + persona.interests 匹配人设
  ├── 检查去重：该人设是否已经写过类似素材
  └── 输出：[(material, persona, target_platforms)] 创作任务队列

阶段 2：内容生成
  ├── 对每个 (素材, 人设, 平台) 组合调用 LLM
  ├── 按平台约束截断/分段/格式化
  ├── 生成配图提示（可选：调用 DALL-E / MidJourney）
  └── 写入 Draft 表，状态 = pending_review

阶段 3：审核（可配置自动/人工）
  ├── 自动审核：敏感词检测 + AI 二次校验（避免幻觉/错误信息）
  ├── 人工审核：推送到管理后台 / IM 通知人工确认
  └── 审核通过 → Content 表，状态 = ready_to_publish

阶段 4：定时发布
  ├── 按 platform.best_publish_times 排入发布队列
  ├── 按 account.rate_limits 控制频率
  ├── 调用 Publisher（API 或 RPA）执行发布
  └── 写入 Post 表，记录 platform_post_id

阶段 5：数据回收
  ├── 定时（每 1h / 6h / 24h）采集已发布内容的互动数据
  ├── 更新 Metrics 表
  └── 每周生成策略优化报告
```

### 3.5 技术选型建议

PostMaker 应当复用 DataRadar 的技术栈以降低维护成本：

| 组件 | 推荐方案 | 理由 |
|------|---------|------|
| 语言 | Python 3.12+ | 与 DataRadar 一致，共享工具链 |
| Web 框架 | FastAPI | 管理后台 API + Webhook 接收 |
| LLM | LiteLLM（复用 DataRadar 的 AIClient） | 多模型支持，切换零成本 |
| 数据库 | PostgreSQL（复用 DataRadar 的实例） | 新增 postmaker schema，共享基础设施 |
| 任务队列 | Redis + 自建轻量调度（或引入 Celery） | 定时发布、数据回收等异步任务 |
| RPA | Playwright（复用 DataRadar 的浏览器实例） | 已有反检测（stealth）经验 |
| 前端 | 可选：Streamlit / Gradio / React | 审核后台、数据面板 |
| 配置 | YAML（复用 ruamel.yaml 模式） | 保持与 DataRadar 一致的管理体验 |

### 3.6 项目结构建议

```
PostMaker/
├── DataRadar/                    # 上游：素材采集（已有）
│
├── PostMaker/                    # 下游：矩阵运营
│   ├── postmaker/
│   │   ├── __init__.py
│   │   ├── __main__.py           # CLI 入口
│   │   │
│   │   ├── persona/              # 人设系统
│   │   │   ├── engine.py         # 人设匹配引擎
│   │   │   └── models.py         # Persona 数据模型
│   │   │
│   │   ├── content/              # 创作引擎
│   │   │   ├── generator.py      # LLM 内容生成
│   │   │   ├── formatter.py      # 平台格式适配
│   │   │   └── reviewer.py       # 自动审核
│   │   │
│   │   ├── publisher/            # 发布引擎
│   │   │   ├── base.py           # Publisher 基类
│   │   │   ├── registry.py       # 发布器注册中心
│   │   │   ├── api/              # API 发布器
│   │   │   │   ├── twitter.py
│   │   │   │   ├── github.py
│   │   │   │   └── medium.py
│   │   │   └── rpa/              # RPA 发布器
│   │   │       ├── wechat.py
│   │   │       ├── zhihu.py
│   │   │       └── xiaohongshu.py
│   │   │
│   │   ├── analytics/            # 数据回收
│   │   │   ├── collector.py      # 各平台数据采集
│   │   │   └── reporter.py       # 策略报告生成
│   │   │
│   │   ├── scheduler/            # 调度系统
│   │   │   └── coordinator.py    # 发布排期协调
│   │   │
│   │   ├── storage/              # 数据层
│   │   │   ├── models.py         # SQLAlchemy / 原生 asyncpg 模型
│   │   │   └── repository.py     # CRUD
│   │   │
│   │   └── integrations/         # 外部集成
│   │       └── dataradar.py      # DataRadar API 客户端
│   │
│   ├── config/
│   │   ├── personas/             # 人设配置目录
│   │   │   ├── tech-reviewer.yaml
│   │   │   └── code-craftsman.yaml
│   │   ├── platforms.yaml        # 平台规则配置
│   │   └── config.yaml           # 主配置
│   │
│   ├── prompts/                  # Prompt 模板
│   │   ├── generate/             # 内容生成 Prompt
│   │   ├── review/               # 审核 Prompt
│   │   └── rewrite/              # 改写 Prompt
│   │
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
└── docs/                         # 跨项目文档
    └── matrix_operations_design.md
```

---

## 四、分阶段实施建议

### Phase 1：最小可用（2-3 周）

**目标**：跑通"素材 → 生成 → 手动发布"链路。

- 实现 Persona 配置加载 + LLM 内容生成
- 对接 DataRadar API 获取素材
- CLI 命令：`postmaker generate --persona tech-reviewer --topic AI`
- 输出到本地文件（Markdown），人工复制粘贴发布

**验证**：能否用不同人设对同一素材产出风格显著不同的内容。

### Phase 2：自动发布（3-4 周）

**目标**：跑通 1-2 个平台的自动发布。

- 先实现有官方 API 的平台（Twitter、GitHub）
- 实现定时发布调度
- 实现发布后数据回收（基础版）
- CLI 命令：`postmaker publish --account twitter:tech_review`

**验证**：全自动从素材到发布，无人工干预。

### Phase 3：RPA + 多平台（4-6 周）

**目标**：覆盖无 API 的国内平台。

- Playwright RPA 发布器（微信公众号、知乎、小红书）
- 反风控策略（人性化延迟、IP 隔离）
- 多账号管理后台（Streamlit/Gradio）
- 审核队列（自动审核 + 人工确认）

### Phase 4：数据闭环（2-3 周）

**目标**：用数据驱动策略优化。

- 完善数据回收（各平台互动数据）
- 策略报告生成（哪个人设 × 哪个平台 × 什么主题效果最好）
- 自动调整发布时间和内容偏好

---

## 五、关键设计原则

1. **人设是一等公民**：整个系统围绕人设组织，不是围绕平台。先问"这个人设怎么看这件事"，再问"这个平台怎么发"。

2. **素材与成稿解耦**：DataRadar 提供的素材是原材料，PostMaker 生成的是加工品。同一素材可以被不同人设加工成完全不同的成品，不存在"一对一"关系。

3. **审核不可跳过**：即使全自动运行，也必须有审核环节（至少是 AI 自审）。LLM 幻觉 + 敏感话题的风险在矩阵规模下会被放大。

4. **平台适配器模式**：每个平台是一个独立的适配器，遵循统一接口。新增平台只需要实现 `Publisher` 接口，不影响核心逻辑。

5. **可回退到手动**：任何环节都可以切换为手动模式。系统的价值是提效，不是取代判断。自动生成的内容应该能导出为人类可编辑的格式。

6. **数据驱动迭代**：不要预设"什么样的内容好"，让数据说话。初期可能人设设计不准、发布时间不优，但持续收集数据后系统会越来越精准。
