"""脚本生成API"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.models import GeneratedScript
from api.schemas import ScriptGenerateRequest, ScriptResponse, MessageResponse
from core.scriptgen.generator import script_generator
from core.logger import get_logger

router = APIRouter()
logger = get_logger("api.script")


@router.post("/generate")
async def generate_script(req: ScriptGenerateRequest):
    """生成视频脚本"""
    result = await script_generator.generate(
        topic=req.topic,
        style_reference=req.style_reference,
        target_platform=req.target_platform,
        target_duration=req.target_duration,
        source_content_ids=req.source_content_ids or None,
        additional_instructions=req.additional_instructions,
    )
    if result:
        return {"message": "脚本生成成功", "data": result}
    raise HTTPException(500, "脚本生成失败")


@router.get("", response_model=list[ScriptResponse])
async def list_scripts(
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取脚本列表"""
    query = select(GeneratedScript)
    if status:
        query = query.where(GeneratedScript.status == status)
    query = query.order_by(GeneratedScript.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: int, db: AsyncSession = Depends(get_db)):
    """获取脚本详情"""
    script = await db.get(GeneratedScript, script_id)
    if not script:
        raise HTTPException(404, "脚本不存在")
    return script


@router.put("/{script_id}/status")
async def update_script_status(
    script_id: int,
    status: str = Query(..., pattern="^(draft|reviewed|final)$"),
    db: AsyncSession = Depends(get_db),
):
    """更新脚本状态"""
    script = await db.get(GeneratedScript, script_id)
    if not script:
        raise HTTPException(404, "脚本不存在")
    script.status = status
    await db.commit()
    return {"message": f"状态已更新为 {status}"}


@router.delete("/{script_id}")
async def delete_script(script_id: int, db: AsyncSession = Depends(get_db)):
    """删除脚本"""
    script = await db.get(GeneratedScript, script_id)
    if not script:
        raise HTTPException(404, "脚本不存在")
    await db.delete(script)
    await db.commit()
    return {"message": "已删除"}
