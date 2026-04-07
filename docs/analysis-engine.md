# 选题分析引擎 - 技术文档

> 本文档描述内容创作系统的 AI 选题分析核心逻辑，可直接迁移到其他项目使用。

---

## 架构概述

```
抓取原始数据 (httpx / yt-dlp)
    ↓
存入数据库 (Content表: 标题/描述/点赞/评论/转发/播放量/标签)
    ↓
第一层: 单条内容分析 → LLM(Prompt + 单条数据) → 存入 TopicAnalysis 表
    ↓
第二层: 博主画像分析 → LLM(Prompt + 全部内容 + 全部单条分析摘要)
第三层: 内容对比分析 → LLM(Prompt + 爆款列表 + 普通列表)
    ↓
导出 Markdown / JSON
```

核心方法：**结构化数据 + Prompt Engineering + JSON mode 输出**。无 embedding、RAG 或微调，纯靠 Prompt 质量驱动分析深度。

---

## LLM 调用方式

使用 OpenAI 兼容接口，支持任意兼容模型（Gemini / DeepSeek / Claude 等）。

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key="your-api-key",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",  # Gemini
)

response = await client.chat.completions.create(
    model="gemini-2.5-flash",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3,
    response_format={"type": "json_object"},  # 强制JSON输出
)
result = json.loads(response.choices[0].message.content)
```

关键点：
- `response_format={"type": "json_object"}` 确保 LLM 只输出合法 JSON
- `temperature=0.3` 降低随机性，保证分析一致性
- 所有 Prompt 末尾加 `只输出JSON，不要其他内容。` 作为兜底

---

## 第一层：单条内容分析

### 输入数据

从数据库取一条内容的结构化字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| title | 标题 | 只要你没在执行，你就是在逃避执行 |
| description | 描述/正文 | 同标题或更长的描述 |
| platform | 平台 | douyin |
| content_type | 类型 | short_video |
| like_count | 点赞数 | 74853 |
| comment_count | 评论数 | 1648 |
| share_count | 转发数 | 17122 |
| view_count | 播放量 | 0 (部分平台不返回) |
| tags | 标签 | 执行力,逃避,拖延 |
| comments | 热门评论(可选) | 评论文本 + 点赞数 |

### Prompt

```
你是一个资深的自媒体内容分析师。请分析以下内容，输出JSON格式的分析结果。

## 待分析内容
- 标题: {title}
- 描述: {description}
- 平台: {platform}
- 类型: {content_type}
- 点赞数: {like_count}
- 评论数: {comment_count}
- 分享数: {share_count}
- 播放量: {view_count}
- 标签: {tags}
{comments_section}

## 请输出以下JSON格式
{
    "topic_category": "选题分类（如：知识分享、情感共鸣、热点追踪、产品测评、生活方式、搞笑娱乐等）",
    "topic_keywords": "核心关键词（逗号分隔，最多5个）",
    "hook_type": "开头hook类型（如：悬念提问、数据冲击、痛点共鸣、反常识、故事开头等）",
    "structure_summary": "内容结构摘要（用100字描述整个内容的结构和逻辑）",
    "engagement_score": 0.0到10.0的互动率评分,
    "replicability_score": 0.0到10.0的可复制性评分,
    "why_popular": "为什么这个内容受欢迎（50字以内）",
    "replication_suggestions": "如何复制这个选题（100字以内的具体建议）"
}

只输出JSON，不要其他内容。
```

### 输出示例

```json
{
    "topic_category": "知识分享",
    "topic_keywords": "执行力,逃避,拖延,自我提升",
    "hook_type": "痛点共鸣",
    "structure_summary": "以极具冲击力的观点开篇，直接点出用户在行动力上的痛点...",
    "engagement_score": 8.8,
    "replicability_score": 8.5,
    "why_popular": "观点犀利，直击用户痛点，引发强烈共鸣与反思",
    "replication_suggestions": "选择一个普遍存在的个人成长痛点，用颠覆性观点作为标题..."
}
```

### 处理逻辑

```python
# 伪代码
content = db.get(Content, content_id)

# 跳过已分析的
if content.is_analyzed:
    return existing_analysis

# 可选：获取热门评论辅助分析
comments = db.query(Comment).filter_by(content_id=id).order_by(like_count.desc()).limit(10)
comments_text = "\n".join(f"- {c.text} (赞{c.like_count})" for c in comments)

# 填充 Prompt → 调用 LLM → 解析 JSON → 存入 TopicAnalysis 表
prompt = ANALYSIS_PROMPT.format(...)
result = await call_llm(prompt)

# 存储
analysis = TopicAnalysis(content_id=id, **result)
db.add(analysis)
content.is_analyzed = True
db.commit()
```

---

## 第二层：博主画像分析

### 输入数据

1. KOL 基本信息（名称、平台、描述）
2. 该 KOL 的**全部内容列表**（按点赞数降序），每条包含：标题、点赞、评论、转发、标签
3. 每条内容的**第一层分析摘要**：分类、Hook类型、互动评分、可复制性评分、关键词

### Prompt

```
你是一个资深的自媒体内容分析师。根据以下博主的全部内容数据，生成博主画像分析报告。

## 博主信息
- 名称: {kol_name}
- 平台: {platform}
- 描述: {description}

## 博主全部内容（共{total}条，按点赞排序）
- 「只要你没在执行，你就是在逃避执行」点赞:74853 评论:1648 转发:17122 标签:执行力,逃避,拖延
- 「你直接赚钱就有钱，间接赚钱永远没钱」点赞:7278 评论:183 转发:1580 标签:商业,创业
- ...（全部内容）

## 各条内容的AI分析摘要
- 「只要你没在执行...」分类:知识分享 Hook:痛点共鸣 互动评分:8.8 可复制性:8.5 关键词:执行力,逃避
- ...（全部已分析内容的摘要）

## 请输出以下JSON格式
{
    "content_expertise": "博主擅长什么内容（200字以内，具体描述博主的内容定位、擅长领域和风格特点）",
    "hook_patterns": "视频的钩子(Hook)模式分析（200字以内，总结博主常用的开头hook类型、哪种hook效果最好、具体举例）",
    "hot_topics": "哪些选题比较火（200字以内，列出数据最好的3-5个选题方向，说明为什么这些方向效果好）",
    "content_style": "内容风格标签（逗号分隔，如：观点犀利,痛点共鸣,实战经验分享）",
    "posting_strategy": "发布策略建议（100字以内，基于数据给出选题和发布建议）"
}

只输出JSON，不要其他内容。
```

### 输出示例

```json
{
    "content_expertise": "DontBeSleeve是一位专注于商业化内容输出的博主，核心定位在于帮助受众提升赚钱能力...",
    "hook_patterns": "博主常用的钩子模式包括"反常识"、"痛点共鸣"和"悬念提问"。其中反常识结合痛点共鸣效果最佳...",
    "hot_topics": "数据表现最好的选题方向：1.赚钱与商业思维的颠覆性认知；2.个人执行力与拖延症；3.AI赋能学习与工作...",
    "content_style": "观点犀利,痛点共鸣,反常识,商业洞察,AI应用",
    "posting_strategy": "建议持续深耕反常识的赚钱思维、商业洞察及AI高效应用等热门选题..."
}
```

### 处理逻辑

```python
# 伪代码
kol = db.get(KOL, kol_id)

# 获取全部内容（按点赞排序）
contents = db.query(Content).filter_by(kol_id=kol_id).order_by(like_count.desc()).all()

# 获取已有的单条分析结果
analyses = db.query(TopicAnalysis, Content).join(...).filter(kol_id=kol_id).all()

# 拼接内容列表文本
contents_list = "\n".join(
    f"- 「{c.title}」点赞:{c.like_count} 评论:{c.comment_count} 转发:{c.share_count} 标签:{c.tags}"
    for c in contents
)

# 拼接分析摘要文本
analyses_list = "\n".join(
    f"- 「{content.title}」分类:{a.topic_category} Hook:{a.hook_type} 互动:{a.engagement_score}"
    for a, content in analyses
)

# 填充 Prompt → 调用 LLM → 返回（不存库，实时生成）
prompt = KOL_PROFILE_PROMPT.format(...)
return await call_llm(prompt)
```

---

## 第三层：内容对比分析

### 输入数据

同一博主的全部内容按点赞数排序后，**前 1/3 为爆款**，**后 1/3 为普通内容**。

### 分组逻辑

```python
contents = db.query(Content).filter_by(kol_id=kol_id).order_by(like_count.desc()).all()

split = max(len(contents) // 3, 1)
top = contents[:split]      # 爆款
bottom = contents[-split:]  # 普通
```

### Prompt

```
你是一个资深的自媒体内容分析师。对比以下同一博主的内容数据，分析爆款和普通内容的差异。

## 博主: {kol_name}

## 爆款内容（数据最好的）
- 「一个人赚不到钱的核心原因就是：上班上多了」
  点赞:127224 评论:1414 转发:34231 播放:0 标签:上班思维,赚钱思维
- 「只要你没在执行，你就是在逃避执行」
  点赞:74853 评论:1648 转发:17122 播放:0 标签:执行力,逃避,拖延

## 普通内容（数据一般的）
- 「付费答疑社群。」
  点赞:358 评论:22 转发:61 播放:0 标签:
- 「dontbesilent 线下课完整介绍（2026）」
  点赞:276 评论:11 转发:30 播放:0 标签:dontbesilent

## 请输出以下JSON格式
{
    "top_analysis": "爆款内容共性分析（200字以内，这些内容为什么爆了，共同特点是什么）",
    "bottom_analysis": "普通内容问题分析（200字以内，这些内容数据为什么一般，问题在哪）",
    "core_differences": "核心差异总结（200字以内，爆款和普通内容的关键区别是什么，3-5个要点）",
    "actionable_tips": "可执行建议（150字以内，基于对比分析，给出具体的改进建议）"
}

只输出JSON，不要其他内容。
```

### 输出示例

```json
{
    "top_analysis": "爆款内容普遍紧扣大众痛点（赚钱、执行力、学习效率），提供颠覆性观点或实用解决方案...",
    "bottom_analysis": "普通内容话题相对小众（特定软件、平台规则），或价值呈现不够直接。部分内容过于技术化...",
    "core_differences": "1.话题广度：爆款聚焦大众痛点，普通偏小众；2.观点冲击力：爆款观点鲜明有争议性...",
    "actionable_tips": "1.深挖大众痛点：围绕赚钱、效率、个人成长；2.观点要独特且有力..."
}
```

---

## 导出格式

### Markdown 导出

完整报告包含三层分析，结构如下：

```markdown
# {KOL名} - 内容分析报告

> 平台: douyin | 内容数: 20 | 已分析: 20

## 1. 博主画像分析
### (a) 擅长什么内容
{content_expertise}
### (b) 视频的 Hook 模式
{hook_patterns}
### (c) 哪些选题比较火
{hot_topics}

## 2. 多条内容对比分析
### (a) 爆款内容
- 列表...
{top_analysis}
### (b) 普通内容
- 列表...
{bottom_analysis}
### (c) 核心差异
{core_differences}

## 3. 选题趋势排行
| # | 标题 | 分类 | Hook | 互动 | 可复制 |
|---|------|------|------|------|--------|
| 1 | xxx  | 知识分享 | 痛点共鸣 | 8.8 | 8.5 |
```

### JSON 导出

```json
{
  "kol_profile": { "content_expertise": "...", "hook_patterns": "...", "hot_topics": "..." },
  "content_comparison": { "top_analysis": "...", "bottom_analysis": "...", "core_differences": "..." },
  "topic_trends": [{ "title": "...", "topic_category": "...", "engagement_score": 8.8 }]
}
```

---

## 迁移清单

要迁移到其他项目，你需要：

1. **三段 Prompt**（本文档中的完整 Prompt 模板）
2. **LLM 调用函数**：OpenAI 兼容接口 + `response_format={"type": "json_object"}`
3. **数据结构**：Content 表（标题/描述/平台/互动数据）+ TopicAnalysis 表（分析结果JSON）
4. **分组逻辑**：对比分析的前1/3后1/3切分

不依赖任何框架特性，换成任何支持 OpenAI 兼容接口的 LLM 都能用。
