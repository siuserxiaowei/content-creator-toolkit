"""KOL管理API"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.models import KOL, Content
from api.schemas import KOLCreate, KOLUpdate, KOLResponse, MessageResponse
from core.logger import get_logger

router = APIRouter()
logger = get_logger("api.kol")


@router.get("", response_model=list[KOLResponse])
async def list_kols(
    platform: Optional[str] = None,
    is_monitoring: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取KOL列表"""
    query = select(KOL)
    if platform:
        query = query.where(KOL.platform == platform)
    if is_monitoring is not None:
        query = query.where(KOL.is_monitoring == is_monitoring)
    query = query.order_by(KOL.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=KOLResponse)
async def create_kol(data: KOLCreate, db: AsyncSession = Depends(get_db)):
    """添加KOL"""
    # 检查重复
    existing = await db.execute(
        select(KOL).where(KOL.platform == data.platform, KOL.platform_uid == data.platform_uid)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "该平台下已存在此KOL")

    kol = KOL(**data.model_dump())
    db.add(kol)
    await db.commit()
    await db.refresh(kol)
    logger.info(f"添加KOL: {kol.name} ({kol.platform})")
    return kol


@router.get("/{kol_id}", response_model=KOLResponse)
async def get_kol(kol_id: int, db: AsyncSession = Depends(get_db)):
    """获取KOL详情"""
    kol = await db.get(KOL, kol_id)
    if not kol:
        raise HTTPException(404, "KOL不存在")
    return kol


@router.put("/{kol_id}", response_model=KOLResponse)
async def update_kol(kol_id: int, data: KOLUpdate, db: AsyncSession = Depends(get_db)):
    """更新KOL"""
    kol = await db.get(KOL, kol_id)
    if not kol:
        raise HTTPException(404, "KOL不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(kol, field, value)
    await db.commit()
    await db.refresh(kol)
    logger.info(f"更新KOL: {kol.name}")
    return kol


@router.delete("/{kol_id}", response_model=MessageResponse)
async def delete_kol(kol_id: int, db: AsyncSession = Depends(get_db)):
    """删除KOL"""
    kol = await db.get(KOL, kol_id)
    if not kol:
        raise HTTPException(404, "KOL不存在")
    await db.delete(kol)
    await db.commit()
    logger.info(f"删除KOL: {kol.name}")
    return MessageResponse(message=f"已删除KOL: {kol.name}")


@router.get("/{kol_id}/stats")
async def get_kol_stats(kol_id: int, db: AsyncSession = Depends(get_db)):
    """获取KOL统计数据"""
    kol = await db.get(KOL, kol_id)
    if not kol:
        raise HTTPException(404, "KOL不存在")

    content_count = await db.scalar(
        select(func.count(Content.id)).where(Content.kol_id == kol_id)
    )
    analyzed_count = await db.scalar(
        select(func.count(Content.id)).where(Content.kol_id == kol_id, Content.is_analyzed == True)
    )
    return {
        "kol_id": kol_id,
        "name": kol.name,
        "total_contents": content_count,
        "analyzed_contents": analyzed_count,
        "last_checked_at": kol.last_checked_at,
    }
