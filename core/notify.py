"""通知系统 - 基于apprise，支持多渠道推送"""

import apprise
from core.logger import get_logger
from config.settings import settings

logger = get_logger("notify")


class Notifier:
    """统一通知推送"""

    def __init__(self):
        self.ap = apprise.Apprise()
        self._setup_channels()

    def _setup_channels(self):
        """根据配置添加通知渠道"""
        # Telegram
        if settings.telegram_bot_token and settings.telegram_chat_id:
            self.ap.add(f"tgram://{settings.telegram_bot_token}/{settings.telegram_chat_id}")
            logger.info("通知渠道: Telegram 已启用")

        # 邮件
        if settings.smtp_host and settings.smtp_user and settings.notify_email:
            self.ap.add(
                f"mailto://{settings.smtp_user}:{settings.smtp_pass}@{settings.smtp_host}:{settings.smtp_port}"
                f"/{settings.notify_email}"
            )
            logger.info("通知渠道: Email 已启用")

    def add_channel(self, url: str):
        """动态添加通知渠道（apprise URL格式）"""
        self.ap.add(url)

    async def send(self, title: str, body: str, notify_type=apprise.NotifyType.INFO):
        """发送通知"""
        try:
            result = await self.ap.async_notify(title=title, body=body, notify_type=notify_type)
            if result:
                logger.info(f"通知发送成功: {title}")
            else:
                logger.warning(f"通知发送失败或无可用渠道: {title}")
            return result
        except Exception as e:
            logger.error(f"通知发送异常: {e}")
            return False

    async def notify_new_content(self, kol_name: str, platform: str, contents: list[dict]):
        """KOL新内容通知"""
        title = f"[{platform}] {kol_name} 发布了新内容"
        lines = []
        for c in contents[:5]:  # 最多显示5条
            lines.append(f"- {c.get('title', '无标题')}")
            if c.get('url'):
                lines.append(f"  {c['url']}")
        if len(contents) > 5:
            lines.append(f"...还有 {len(contents) - 5} 条")
        body = "\n".join(lines)
        await self.send(title, body)

    async def notify_analysis_done(self, kol_name: str, topic_summary: str):
        """选题分析完成通知"""
        title = f"选题分析完成: {kol_name}"
        await self.send(title, topic_summary)

    async def notify_script_generated(self, script_title: str):
        """脚本生成完成通知"""
        title = "视频脚本已生成"
        await self.send(title, f"脚本: {script_title}")


# 全局单例
notifier = Notifier()
