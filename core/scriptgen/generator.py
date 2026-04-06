"""视频脚本生成器 - LLM驱动，根据选题自动生成视频脚本"""

import json
from openai import AsyncOpenAI
from sqlalchemy import select

from config.settings import settings
from storage.database import async_session
from storage.models import Content, TopicAnalysis, GeneratedScript
from core.logger import get_logger
from core.notify import notifier

logger = get_logger("scriptgen")

SCRIPT_PROMPT = """你是一个顶级的短视频编剧。请根据以下信息生成一个完整的视频脚本。

## 创作要求
- 选题: {topic}
- 目标平台: {target_platform}
- 目标时长: {target_duration}秒
- 风格参考: {style_reference}
- 额外要求: {additional_instructions}

{reference_section}

## 输出格式（JSON）
{{
    "title": "视频标题（吸引人点击，15字以内）",
    "hook": "开头hook（前3秒，必须立刻抓住观众注意力，写出具体的台词/画面描述）",
    "body": "正文内容（分段落，每段包含：[画面描述] + 台词/旁白。注意节奏感和信息密度）",
    "cta": "结尾CTA（引导关注/点赞/评论，自然不生硬）",
    "visual_notes": "画面建议（拍摄手法、转场、特效等简要建议）",
    "bgm_suggestion": "BGM建议（风格/节奏建议）",
    "estimated_duration": 预估时长秒数
}}

要求：
1. hook必须在3秒内制造悬念或冲突
2. 正文要有明确的结构（问题-方案-结果，或故事弧线）
3. 语言口语化，像真人说话
4. 根据平台特性调整风格（抖音要快节奏、B站可以深度些）
5. 只输出JSON"""


class ScriptGenerator:
    """视频脚本生成器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.openai_model

    async def generate(
        self,
        topic: str,
        style_reference: str = "",
        target_platform: str = "douyin",
        target_duration: int = 60,
        source_content_ids: list[int] | None = None,
        additional_instructions: str = "",
    ) -> dict | None:
        """生成视频脚本"""

        # 获取参考内容的分析结果
        reference_text = ""
        if source_content_ids:
            reference_text = await self._build_reference(source_content_ids)

        platform_names = {
            "douyin": "抖音（竖屏短视频，快节奏，15-60秒为主）",
            "bilibili": "B站（横屏，可以稍长，1-5分钟，观众接受深度内容）",
            "xhs": "小红书（图文+视频，种草风格，真实感很重要）",
            "kuaishou": "快手（接地气，真实，生活化）",
            "weibo": "微博（话题性强，容易引发讨论）",
        }

        prompt = SCRIPT_PROMPT.format(
            topic=topic,
            target_platform=platform_names.get(target_platform, target_platform),
            target_duration=target_duration,
            style_reference=style_reference or "无特定参考",
            additional_instructions=additional_instructions or "无",
            reference_section=reference_text,
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            result_text = response.choices[0].message.content
            script_data = json.loads(result_text)

            # 组合完整脚本
            full_script = self._compose_full_script(script_data)

            # 存储
            async with async_session() as db:
                script = GeneratedScript(
                    title=script_data.get("title", topic),
                    topic=topic,
                    style_reference=style_reference,
                    target_platform=target_platform,
                    target_duration=target_duration,
                    hook=script_data.get("hook", ""),
                    body=script_data.get("body", ""),
                    cta=script_data.get("cta", ""),
                    full_script=full_script,
                    source_content_ids=source_content_ids,
                    metadata={
                        "visual_notes": script_data.get("visual_notes", ""),
                        "bgm_suggestion": script_data.get("bgm_suggestion", ""),
                        "estimated_duration": script_data.get("estimated_duration"),
                    },
                )
                db.add(script)
                await db.commit()
                await db.refresh(script)

                logger.info(f"脚本生成完成: {script.title}")
                await notifier.notify_script_generated(script.title)

                return {
                    "id": script.id,
                    "title": script.title,
                    "hook": script.hook,
                    "body": script.body,
                    "cta": script.cta,
                    "full_script": full_script,
                    "visual_notes": script_data.get("visual_notes", ""),
                    "bgm_suggestion": script_data.get("bgm_suggestion", ""),
                }

        except Exception as e:
            logger.error(f"脚本生成失败: {e}")
            return None

    async def _build_reference(self, content_ids: list[int]) -> str:
        """构建参考内容文本"""
        async with async_session() as db:
            lines = ["\n## 参考内容分析"]
            for cid in content_ids[:5]:
                content = await db.get(Content, cid)
                if not content:
                    continue
                analysis = await db.execute(
                    select(TopicAnalysis).where(TopicAnalysis.content_id == cid)
                )
                ta = analysis.scalar_one_or_none()

                lines.append(f"\n### 参考{cid}: {content.title}")
                lines.append(f"- 平台: {content.platform}")
                lines.append(f"- 互动: 赞{content.like_count} 评论{content.comment_count} 播放{content.view_count}")
                if ta:
                    lines.append(f"- 选题分类: {ta.topic_category}")
                    lines.append(f"- Hook类型: {ta.hook_type}")
                    lines.append(f"- 结构: {ta.structure_summary}")
                    if ta.analysis_detail:
                        lines.append(f"- 火爆原因: {ta.analysis_detail.get('why_popular', '')}")

            return "\n".join(lines)

    def _compose_full_script(self, data: dict) -> str:
        """组合完整脚本文本"""
        parts = []
        parts.append(f"# {data.get('title', '未命名')}\n")
        parts.append("## 开头Hook")
        parts.append(data.get("hook", "") + "\n")
        parts.append("## 正文")
        parts.append(data.get("body", "") + "\n")
        parts.append("## 结尾CTA")
        parts.append(data.get("cta", "") + "\n")
        if data.get("visual_notes"):
            parts.append("---")
            parts.append(f"画面建议: {data['visual_notes']}")
        if data.get("bgm_suggestion"):
            parts.append(f"BGM建议: {data['bgm_suggestion']}")
        return "\n".join(parts)


script_generator = ScriptGenerator()
