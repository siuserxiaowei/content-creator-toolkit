"""选题分析API"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.models import TopicAnalysis
from api.schemas import AnalysisRequest, TopicAnalysisResponse, MessageResponse
from core.analyzer.topic_analyzer import topic_analyzer
from core.logger import get_logger

router = APIRouter()
logger = get_logger("api.analysis")


@router.post("/analyze", response_model=MessageResponse)
async def trigger_analysis(req: AnalysisRequest):
    """触发选题分析"""
    if req.content_id:
        try:
            result = await topic_analyzer.analyze_content(req.content_id)
            if result:
                return MessageResponse(message="分析完成", data=result)
            return MessageResponse(message="分析失败: 未知错误")
        except RuntimeError as e:
            return MessageResponse(message=f"分析失败: {e}")

    if req.kol_id:
        try:
            results = await topic_analyzer.analyze_kol_contents(req.kol_id)
            return MessageResponse(
                message=f"批量分析完成，共分析 {len(results)} 条内容",
                data={"count": len(results)},
            )
        except RuntimeError as e:
            return MessageResponse(message=f"分析失败: {e}")

    return MessageResponse(message="请指定content_id或kol_id")


@router.get("/trends")
async def get_trends(
    platform: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取选题趋势"""
    trends = await topic_analyzer.get_topic_trends(platform=platform, limit=limit)
    return {"total": len(trends), "items": trends}


@router.get("/results", response_model=list[TopicAnalysisResponse])
async def list_analyses(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取分析结果列表"""
    result = await db.execute(
        select(TopicAnalysis).order_by(TopicAnalysis.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
