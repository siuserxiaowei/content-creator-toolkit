"""KOL监控引擎 - 定时检查KOL主页，发现新内容触发爬取和通知"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import async_session
from storage.models import KOL, Content, MonitorLog
from core.logger import get_logger
from core.notify import notifier

logger = get_logger("monitor")


class MonitorEngine:
    """监控引擎：检查KOL是否发布新内容"""

    async def check_kol(self, kol_id: int, check_type: str = "scheduled") -> dict:
        """检查单个KOL的新内容"""
        async with async_session() as db:
            kol = await db.get(KOL, kol_id)
            if not kol:
                logger.warning(f"KOL不存在: {kol_id}")
                return {"status": "failed", "message": "KOL不存在"}

            if not kol.is_monitoring:
                return {"status": "skipped", "message": "监控已暂停"}

            logger.info(f"开始检查KOL: {kol.name} ({kol.platform})")

            try:
                # 调用对应平台的爬虫获取最新内容
                from core.crawler.factory import CrawlerFactory
                crawler = CrawlerFactory.get_crawler(kol.platform)
                new_items = await crawler.fetch_user_posts(
                    user_id=kol.platform_uid,
                    cookie=self._get_cookie(kol.platform),
                )

                # 对比数据库，找出新内容
                new_contents = []
                for item in new_items:
                    existing = await db.execute(
                        select(Content).where(
                            Content.platform == kol.platform,
                            Content.content_id == item["content_id"],
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    content = Content(
                        kol_id=kol.id,
                        platform=kol.platform,
                        content_type=item.get("content_type", "video"),
                        content_id=item["content_id"],
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        url=item.get("url", ""),
                        cover_url=item.get("cover_url", ""),
                        media_urls=item.get("media_urls"),
                        tags=item.get("tags", ""),
                        like_count=item.get("like_count", 0),
                        comment_count=item.get("comment_count", 0),
                        share_count=item.get("share_count", 0),
                        view_count=item.get("view_count", 0),
                        published_at=item.get("published_at"),
                        raw_data=item.get("raw_data"),
                    )
                    db.add(content)
                    new_contents.append(item)

                # 更新KOL检查时间
                kol.last_checked_at = datetime.utcnow()

                # 记录日志
                status = "changed" if new_contents else "unchanged"
                log = MonitorLog(
                    kol_id=kol.id,
                    check_type=check_type,
                    status=status,
                    new_contents_count=len(new_contents),
                    message=f"发现 {len(new_contents)} 条新内容" if new_contents else "无新内容",
                )
                db.add(log)
                await db.commit()

                # 发送通知
                if new_contents:
                    logger.info(f"KOL {kol.name} 发现 {len(new_contents)} 条新内容")
                    await notifier.notify_new_content(kol.name, kol.platform, new_contents)
                else:
                    logger.debug(f"KOL {kol.name} 无新内容")

                return {
                    "status": status,
                    "new_contents_count": len(new_contents),
                    "message": log.message,
                }

            except Exception as e:
                logger.error(f"检查KOL {kol.name} 失败: {e}")
                log = MonitorLog(
                    kol_id=kol.id,
                    check_type=check_type,
                    status="failed",
                    message=str(e),
                )
                db.add(log)
                kol.last_checked_at = datetime.utcnow()
                await db.commit()
                return {"status": "failed", "message": str(e)}

    async def check_all(self):
        """检查所有启用监控的KOL"""
        async with async_session() as db:
            result = await db.execute(
                select(KOL).where(KOL.is_monitoring == True)
            )
            kols = result.scalars().all()

        logger.info(f"开始全量检查，共 {len(kols)} 个KOL")
        results = []
        for kol in kols:
            r = await self.check_kol(kol.id)
            results.append({"kol_id": kol.id, "name": kol.name, **r})
        return results

    def _get_cookie(self, platform: str) -> str:
        """获取平台cookie"""
        from config.settings import settings
        cookie_map = {
            "xhs": settings.xhs_cookie,
            "douyin": settings.douyin_cookie,
            "bilibili": settings.bilibili_cookie,
            "weibo": settings.weibo_cookie,
        }
        return cookie_map.get(platform, "")


monitor_engine = MonitorEngine()
