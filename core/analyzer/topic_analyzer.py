"""选题分析引擎 - LLM驱动，分析KOL内容的选题策略"""
from __future__ import annotations

import json
from datetime import datetime
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from storage.database import async_session
from storage.models import Content, TopicAnalysis, KOL
from core.logger import get_logger
from core.notify import notifier

logger = get_logger("analyzer")

ANALYSIS_PROMPT = """你是一个资深的自媒体内容分析师。请分析以下内容，输出JSON格式的分析结果。

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
{{
    "topic_category": "选题分类（如：知识分享、情感共鸣、热点追踪、产品测评、生活方式、搞笑娱乐等）",
    "topic_keywords": "核心关键词（逗号分隔，最多5个）",
    "hook_type": "开头hook类型（如：悬念提问、数据冲击、痛点共鸣、反常识、故事开头等）",
    "structure_summary": "内容结构摘要（用100字描述整个内容的结构和逻辑）",
    "engagement_score": 0.0到10.0的互动率评分,
    "replicability_score": 0.0到10.0的可复制性评分,
    "why_popular": "为什么这个内容受欢迎（50字以内）",
    "replication_suggestions": "如何复制这个选题（100字以内的具体建议）"
}}

只输出JSON，不要其他内容。"""


KOL_PROFILE_PROMPT = """你是一个资深的自媒体内容分析师。根据以下博主的全部内容数据，生成博主画像分析报告。

## 博主信息
- 名称: {kol_name}
- 平台: {platform}
- 描述: {description}

## 博主全部内容（共{total}条，按点赞排序）
{contents_list}

## 各条内容的AI分析摘要
{analyses_list}

## 请输出以下JSON格式
{{
    "content_expertise": "博主擅长什么内容（200字以内，具体描述博主的内容定位、擅长领域和风格特点）",
    "hook_patterns": "视频的钩子(Hook)模式分析（200字以内，总结博主常用的开头hook类型、哪种hook效果最好、具体举例）",
    "hot_topics": "哪些选题比较火（200字以内，列出数据最好的3-5个选题方向，说明为什么这些方向效果好）",
    "content_style": "内容风格标签（逗号分隔，如：观点犀利,痛点共鸣,实战经验分享）",
    "posting_strategy": "发布策略建议（100字以内，基于数据给出选题和发布建议）"
}}

只输出JSON，不要其他内容。"""


COMPARE_PROMPT = """你是一个资深的自媒体内容分析师。对比以下同一博主的内容数据，分析爆款和普通内容的差异。

## 博主: {kol_name}

## 爆款内容（数据最好的）
{top_contents}

## 普通内容（数据一般的）
{bottom_contents}

## 请输出以下JSON格式
{{
    "top_analysis": "爆款内容共性分析（200字以内，这些内容为什么爆了，共同特点是什么）",
    "bottom_analysis": "普通内容问题分析（200字以内，这些内容数据为什么一般，问题在哪）",
    "core_differences": "核心差异总结（200字以内，爆款和普通内容的关键区别是什么，3-5个要点）",
    "actionable_tips": "可执行建议（150字以内，基于对比分析，给出具体的改进建议）"
}}

只输出JSON，不要其他内容。"""


class TopicAnalyzer:
    """选题分析器"""

    def __init__(self):
        self._client = None
        self.model = settings.openai_model

    @property
    def client(self):
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key or "sk-placeholder",
                base_url=settings.openai_base_url,
            )
        return self._client

    def _check_api_key(self):
        if not settings.openai_api_key or settings.openai_api_key.startswith("your-"):
            raise ValueError("未配置 OPENAI_API_KEY，请在 .env 中设置有效的 API Key")

    async def _call_llm(self, prompt: str) -> dict:
        """统一的LLM调用"""
        self._check_api_key()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    async def analyze_content(self, content_id: int) -> dict | None:
        """分析单条内容的选题"""
        async with async_session() as db:
            content = await db.get(Content, content_id)
            if not content:
                logger.warning(f"内容不存在: {content_id}")
                return None

            if content.is_analyzed:
                logger.info(f"内容已分析过: {content_id}")
                existing = await db.execute(
                    select(TopicAnalysis).where(TopicAnalysis.content_id == content_id)
                )
                result = existing.scalar_one_or_none()
                return result.analysis_detail if result else None

            # 获取热门评论作为辅助分析
            from storage.models import Comment
            comments_result = await db.execute(
                select(Comment)
                .where(Comment.content_id == content_id)
                .order_by(Comment.like_count.desc())
                .limit(10)
            )
            top_comments = comments_result.scalars().all()
            comments_text = ""
            if top_comments:
                comments_text = "\n## 热门评论\n" + "\n".join(
                    f"- {c.text} (赞{c.like_count})" for c in top_comments
                )

            prompt = ANALYSIS_PROMPT.format(
                title=content.title,
                description=content.description[:1000],
                platform=content.platform,
                content_type=content.content_type,
                like_count=content.like_count,
                comment_count=content.comment_count,
                share_count=content.share_count,
                view_count=content.view_count,
                tags=content.tags,
                comments_section=comments_text,
            )

            try:
                analysis_data = await self._call_llm(prompt)

                analysis = TopicAnalysis(
                    content_id=content_id,
                    topic_category=analysis_data.get("topic_category", ""),
                    topic_keywords=analysis_data.get("topic_keywords", ""),
                    hook_type=analysis_data.get("hook_type", ""),
                    structure_summary=analysis_data.get("structure_summary", ""),
                    engagement_score=float(analysis_data.get("engagement_score", 0)),
                    replicability_score=float(analysis_data.get("replicability_score", 0)),
                    analysis_detail=analysis_data,
                )
                db.add(analysis)
                content.is_analyzed = True
                await db.commit()

                logger.info(f"内容分析完成: {content.title[:30]}...")
                return analysis_data

            except Exception as e:
                logger.error(f"LLM分析失败: {e}")
                raise RuntimeError(str(e))

    async def analyze_kol_contents(self, kol_id: int, limit: int = 20) -> list[dict]:
        """批量分析某KOL的未分析内容"""
        async with async_session() as db:
            kol = await db.get(KOL, kol_id)
            if not kol:
                return []

            result = await db.execute(
                select(Content)
                .where(Content.kol_id == kol_id, Content.is_analyzed == False)
                .order_by(Content.created_at.desc())
                .limit(limit)
            )
            contents = result.scalars().all()

        logger.info(f"开始分析KOL {kol.name} 的 {len(contents)} 条内容")
        results = []
        for content in contents:
            try:
                r = await self.analyze_content(content.id)
                if r:
                    results.append(r)
            except RuntimeError:
                raise
            except Exception as e:
                logger.warning(f"跳过内容 {content.id}: {e}")
                continue

        if results:
            await notifier.notify_analysis_done(
                kol.name,
                f"已分析 {len(results)} 条内容，主要选题: {', '.join(set(r.get('topic_category', '') for r in results[:5]))}"
            )

        return results

    async def analyze_kol_profile(self, kol_id: int) -> dict:
        """博主画像分析 - 擅长什么内容、Hook模式、哪些选题火"""
        async with async_session() as db:
            kol = await db.get(KOL, kol_id)
            if not kol:
                raise ValueError("KOL不存在")

            # 获取全部内容（按点赞排序）
            result = await db.execute(
                select(Content)
                .where(Content.kol_id == kol_id)
                .order_by(Content.like_count.desc())
            )
            contents = result.scalars().all()
            if not contents:
                raise ValueError("该KOL暂无内容数据，请先抓取内容")

            # 获取已有分析
            analysis_result = await db.execute(
                select(TopicAnalysis, Content)
                .join(Content, TopicAnalysis.content_id == Content.id)
                .where(Content.kol_id == kol_id)
                .order_by(Content.like_count.desc())
            )
            analyses = analysis_result.all()

        # 构建内容列表
        contents_list = "\n".join(
            f"- 「{c.title}」点赞:{c.like_count} 评论:{c.comment_count} 转发:{c.share_count} 标签:{c.tags}"
            for c in contents
        )

        # 构建分析摘要
        analyses_list = "\n".join(
            f"- 「{content.title}」分类:{analysis.topic_category} Hook:{analysis.hook_type} "
            f"互动评分:{analysis.engagement_score} 可复制性:{analysis.replicability_score} "
            f"关键词:{analysis.topic_keywords}"
            for analysis, content in analyses
        ) if analyses else "（暂无分析数据，请基于原始内容数据分析）"

        prompt = KOL_PROFILE_PROMPT.format(
            kol_name=kol.name,
            platform=kol.platform,
            description=kol.description,
            total=len(contents),
            contents_list=contents_list,
            analyses_list=analyses_list,
        )

        try:
            profile_data = await self._call_llm(prompt)
            profile_data["kol_name"] = kol.name
            profile_data["platform"] = kol.platform
            profile_data["total_contents"] = len(contents)
            profile_data["analyzed_count"] = len(analyses)
            profile_data["generated_at"] = datetime.now().isoformat()
            return profile_data
        except Exception as e:
            raise RuntimeError(str(e))

    async def compare_contents(self, kol_id: int) -> dict:
        """多条内容对比分析 - 爆款vs普通内容的差异"""
        async with async_session() as db:
            kol = await db.get(KOL, kol_id)
            if not kol:
                raise ValueError("KOL不存在")

            # 获取全部内容按点赞排序
            result = await db.execute(
                select(Content)
                .where(Content.kol_id == kol_id)
                .order_by(Content.like_count.desc())
            )
            contents = result.scalars().all()
            if len(contents) < 3:
                raise ValueError("内容数量不足（至少需要3条），请先抓取更多内容")

        # 分成爆款（前1/3）和普通（后1/3）
        split = max(len(contents) // 3, 1)
        top = contents[:split]
        bottom = contents[-split:]

        def fmt(c):
            return (
                f"- 「{c.title}」\n"
                f"  点赞:{c.like_count} 评论:{c.comment_count} 转发:{c.share_count} "
                f"播放:{c.view_count} 标签:{c.tags}"
            )

        prompt = COMPARE_PROMPT.format(
            kol_name=kol.name,
            top_contents="\n".join(fmt(c) for c in top),
            bottom_contents="\n".join(fmt(c) for c in bottom),
        )

        try:
            compare_data = await self._call_llm(prompt)
            compare_data["kol_name"] = kol.name
            compare_data["top_items"] = [
                {"title": c.title, "like_count": c.like_count, "comment_count": c.comment_count,
                 "share_count": c.share_count}
                for c in top
            ]
            compare_data["bottom_items"] = [
                {"title": c.title, "like_count": c.like_count, "comment_count": c.comment_count,
                 "share_count": c.share_count}
                for c in bottom
            ]
            compare_data["generated_at"] = datetime.now().isoformat()
            return compare_data
        except Exception as e:
            raise RuntimeError(str(e))

    async def export_kol_report(self, kol_id: int, fmt: str = "markdown") -> str:
        """导出KOL完整分析报告"""
        # 获取画像和对比数据
        profile = await self.analyze_kol_profile(kol_id)
        compare = await self.compare_contents(kol_id)
        trends = await self.get_topic_trends(limit=50)
        # 只保留该KOL的趋势
        async with async_session() as db:
            kol = await db.get(KOL, kol_id)
            kol_content_ids = [t["content_id"] for t in trends]
            result = await db.execute(
                select(Content.id).where(Content.kol_id == kol_id)
            )
            my_ids = set(row[0] for row in result.all())
        kol_trends = [t for t in trends if t["content_id"] in my_ids]

        if fmt == "json":
            return json.dumps({
                "kol_profile": profile,
                "content_comparison": compare,
                "topic_trends": kol_trends,
            }, ensure_ascii=False, indent=2)

        # Markdown
        md = f"""# {profile['kol_name']} - 内容分析报告

> 平台: {profile['platform']} | 内容数: {profile['total_contents']} | 已分析: {profile['analyzed_count']}
> 生成时间: {profile['generated_at']}

---

## 1. 博主画像分析

### (a) 擅长什么内容
{profile['content_expertise']}

### (b) 视频的 Hook 模式
{profile['hook_patterns']}

### (c) 哪些选题比较火
{profile['hot_topics']}

**风格标签:** {profile.get('content_style', '')}

**发布策略建议:** {profile.get('posting_strategy', '')}

---

## 2. 多条内容对比分析

### (a) 爆款内容（数据最好）
"""
        for item in compare.get("top_items", []):
            md += f"- 「{item['title']}」 赞:{item['like_count']} 评论:{item['comment_count']} 转发:{item['share_count']}\n"

        md += f"""
**爆款共性:** {compare['top_analysis']}

### (b) 普通内容（数据一般）
"""
        for item in compare.get("bottom_items", []):
            md += f"- 「{item['title']}」 赞:{item['like_count']} 评论:{item['comment_count']} 转发:{item['share_count']}\n"

        md += f"""
**问题分析:** {compare['bottom_analysis']}

### (c) 核心差异
{compare['core_differences']}

**改进建议:** {compare['actionable_tips']}

---

## 3. 选题趋势排行

| # | 标题 | 分类 | Hook | 互动 | 可复制 |
|---|------|------|------|------|--------|
"""
        for i, t in enumerate(kol_trends[:20], 1):
            md += f"| {i} | {t['title'][:30]} | {t['topic_category']} | {t.get('hook_type','')} | {t['engagement_score']} | {t['replicability_score']} |\n"

        return md

    async def get_topic_trends(self, platform: str | None = None, limit: int = 20) -> list[dict]:
        """获取选题趋势（按可复制性和互动率排序）"""
        async with async_session() as db:
            query = (
                select(TopicAnalysis, Content)
                .join(Content, TopicAnalysis.content_id == Content.id)
                .order_by(TopicAnalysis.replicability_score.desc())
                .limit(limit)
            )
            if platform:
                query = query.where(Content.platform == platform)
            result = await db.execute(query)
            rows = result.all()

        return [
            {
                "content_id": content.id,
                "title": content.title,
                "platform": content.platform,
                "url": content.url,
                "topic_category": analysis.topic_category,
                "topic_keywords": analysis.topic_keywords,
                "engagement_score": analysis.engagement_score,
                "replicability_score": analysis.replicability_score,
                "hook_type": analysis.hook_type,
                "why_popular": (analysis.analysis_detail or {}).get("why_popular", ""),
                "replication_suggestions": (analysis.analysis_detail or {}).get("replication_suggestions", ""),
            }
            for analysis, content in rows
        ]


topic_analyzer = TopicAnalyzer()
