"""选题分析引擎 - LLM驱动，分析KOL内容的选题策略"""

import json
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


class TopicAnalyzer:
    """选题分析器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.openai_model

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

            # 调用LLM分析
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
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                result_text = response.choices[0].message.content
                analysis_data = json.loads(result_text)

                # 存储分析结果
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

                logger.info(f"内容分析完成: {content.title[:30]}... 分类={analysis_data.get('topic_category')}")
                return analysis_data

            except Exception as e:
                logger.error(f"LLM分析失败: {e}")
                return None

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
            r = await self.analyze_content(content.id)
            if r:
                results.append(r)

        if results:
            await notifier.notify_analysis_done(
                kol.name,
                f"已分析 {len(results)} 条内容，主要选题: {', '.join(set(r.get('topic_category', '') for r in results[:5]))}"
            )

        return results

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
