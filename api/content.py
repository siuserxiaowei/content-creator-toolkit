"""内容管理API"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.models import Content, Comment
from api.schemas import ContentResponse, ContentListResponse
from core.logger import get_logger

router = APIRouter()
logger = get_logger("api.content")


@router.get("", response_model=ContentListResponse)
async def list_contents(
    kol_id: int | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    is_analyzed: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取内容列表（分页）"""
    query = select(Content)
    count_query = select(func.count(Content.id))

    if kol_id:
        query = query.where(Content.kol_id == kol_id)
        count_query = count_query.where(Content.kol_id == kol_id)
    if platform:
        query = query.where(Content.platform == platform)
        count_query = count_query.where(Content.platform == platform)
    if content_type:
        query = query.where(Content.content_type == content_type)
        count_query = count_query.where(Content.content_type == content_type)
    if is_analyzed is not None:
        query = query.where(Content.is_analyzed == is_analyzed)
        count_query = count_query.where(Content.is_analyzed == is_analyzed)

    total = await db.scalar(count_query)
    query = query.order_by(Content.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)

    return ContentListResponse(total=total or 0, items=result.scalars().all())


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: int, db: AsyncSession = Depends(get_db)):
    """获取内容详情"""
    content = await db.get(Content, content_id)
    if not content:
        raise HTTPException(404, "内容不存在")
    return content


@router.get("/{content_id}/comments")
async def get_content_comments(
    content_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取内容评论"""
    content = await db.get(Content, content_id)
    if not content:
        raise HTTPException(404, "内容不存在")

    total = await db.scalar(
        select(func.count(Comment.id)).where(Comment.content_id == content_id)
    )
    result = await db.execute(
        select(Comment)
        .where(Comment.content_id == content_id)
        .order_by(Comment.like_count.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    comments = result.scalars().all()
    return {
        "total": total or 0,
        "items": [
            {
                "id": c.id,
                "user_name": c.user_name,
                "text": c.text,
                "like_count": c.like_count,
                "published_at": c.published_at,
            }
            for c in comments
        ],
    }


@router.delete("/{content_id}")
async def delete_content(content_id: int, db: AsyncSession = Depends(get_db)):
    """删除内容"""
    content = await db.get(Content, content_id)
    if not content:
        raise HTTPException(404, "内容不存在")
    await db.delete(content)
    await db.commit()
    return {"message": "已删除"}
