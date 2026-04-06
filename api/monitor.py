"""监控管理API"""

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
    kol_id: int | None = None,
    status: str | None = None,
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
    return {
        "total_kols": total_kols or 0,
        "active_kols": active_kols or 0,
        "total_checks": total_checks or 0,
        "recent_changes": recent_changes or 0,
    }
