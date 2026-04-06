"""调度引擎 - APScheduler驱动的自动化任务调度"""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from storage.database import async_session
from storage.models import KOL
from core.logger import get_logger

logger = get_logger("scheduler")

scheduler = AsyncIOScheduler()


async def scheduled_check_all():
    """定时任务：检查所有KOL"""
    from core.monitor.engine import monitor_engine
    logger.info("定时任务触发：全量KOL检查")
    try:
        results = await monitor_engine.check_all()
        changed = sum(1 for r in results if r.get("status") == "changed")
        logger.info(f"定时检查完成: {len(results)}个KOL, {changed}个有更新")
    except Exception as e:
        logger.error(f"定时检查失败: {e}")


async def scheduled_auto_analyze():
    """定时任务：自动分析未分析的内容"""
    from core.analyzer.topic_analyzer import topic_analyzer
    from storage.models import Content

    async with async_session() as db:
        result = await db.execute(
            select(Content)
            .where(Content.is_analyzed == False)
            .order_by(Content.created_at.desc())
            .limit(10)
        )
        contents = result.scalars().all()

    if not contents:
        return

    logger.info(f"定时任务：自动分析 {len(contents)} 条未分析内容")
    for content in contents:
        try:
            await topic_analyzer.analyze_content(content.id)
        except Exception as e:
            logger.error(f"自动分析内容 {content.id} 失败: {e}")


async def start_scheduler():
    """启动调度器"""
    # 每30分钟检查一次所有KOL
    scheduler.add_job(
        scheduled_check_all,
        IntervalTrigger(minutes=30),
        id="check_all_kols",
        name="全量KOL检查",
        replace_existing=True,
    )

    # 每小时自动分析未分析的内容
    scheduler.add_job(
        scheduled_auto_analyze,
        IntervalTrigger(hours=1),
        id="auto_analyze",
        name="自动选题分析",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("调度器已启动: 每30分钟检查KOL, 每小时自动分析")


def get_scheduler_jobs() -> list[dict]:
    """获取当前调度任务列表"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs
