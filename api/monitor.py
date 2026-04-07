"""监控管理API"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.models import MonitorLog, KOL
from api.schemas import MonitorTriggerRequest, MonitorLogResponse, MessageResponse
from core.monitor.engine import monitor_engine
from core.logger import get_logger

router = APIRouter()
logger = get_logger("api.monitor")


@router.post("/check", response_model=MessageResponse)
async def trigger_check(req: MonitorTriggerRequest):
    """手动触发KOL检查"""
    result = await monitor_engine.check_kol(req.kol_id, check_type="manual")
    return MessageResponse(message=result["message"], data=result)


@router.post("/check-all", response_model=MessageResponse)
async def trigger_check_all():
    """手动触发全量检查"""
    results = await monitor_engine.check_all()
    changed = sum(1 for r in results if r["status"] == "changed")
    return MessageResponse(
        message=f"检查完成: {len(results)}个KOL, {changed}个有新内容",
        data={"results": results},
    )


@router.get("/logs", response_model=list[MonitorLogResponse])
async def list_monitor_logs(
    kol_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取监控日志"""
    query = select(MonitorLog)
    if kol_id:
        query = query.where(MonitorLog.kol_id == kol_id)
    if status:
        query = query.where(MonitorLog.status == status)
    query = query.order_by(MonitorLog.checked_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/dashboard")
async def monitor_dashboard(db: AsyncSession = Depends(get_db)):
    """监控仪表盘数据"""
    total_kols = await db.scalar(select(func.count(KOL.id)))
    active_kols = await db.scalar(select(func.count(KOL.id)).where(KOL.is_monitoring == True))
    total_checks = await db.scalar(select(func.count(MonitorLog.id)))
    recent_changes = await db.scalar(
        select(func.count(MonitorLog.id)).where(MonitorLog.status == "changed")
    )
    # 内容统计
    from storage.models import Content, TopicAnalysis
    total_contents = await db.scalar(select(func.count(Content.id)))
    analyzed_contents = await db.scalar(select(func.count(Content.id)).where(Content.is_analyzed == True))

    # 各平台内容数量
    platform_stats = {}
    for p in ["xhs", "douyin", "bilibili", "weibo", "youtube", "twitter", "tiktok", "instagram"]:
        cnt = await db.scalar(select(func.count(Content.id)).where(Content.platform == p))
        if cnt:
            platform_stats[p] = cnt

    # 选题分类统计
    topic_stats_result = await db.execute(
        select(TopicAnalysis.topic_category, func.count(TopicAnalysis.id))
        .group_by(TopicAnalysis.topic_category)
        .order_by(func.count(TopicAnalysis.id).desc())
        .limit(10)
    )
    topic_categories = [{"name": r[0] or "未分类", "count": r[1]} for r in topic_stats_result.all()]

    # 最近内容的互动数据（用于柱状图）
    recent_contents_result = await db.execute(
        select(Content.title, Content.like_count, Content.comment_count, Content.view_count, Content.platform)
        .order_by(Content.created_at.desc()).limit(10)
    )
    recent_engagement = [
        {"title": r[0][:20] if r[0] else "无标题", "likes": r[1], "comments": r[2], "views": r[3], "platform": r[4]}
        for r in recent_contents_result.all()
    ]

    return {
        "total_kols": total_kols or 0,
        "active_kols": active_kols or 0,
        "total_checks": total_checks or 0,
        "recent_changes": recent_changes or 0,
        "total_contents": total_contents or 0,
        "analyzed_contents": analyzed_contents or 0,
        "platform_stats": platform_stats,
        "topic_categories": topic_categories,
        "recent_engagement": recent_engagement,
    }
