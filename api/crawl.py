"""爬取操作API - 用户主动触发抓取"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db, async_session
from storage.models import KOL, Content, Comment
from core.crawler.factory import CrawlerFactory
from core.logger import get_logger
from config.settings import settings

router = APIRouter()
logger = get_logger("api.crawl")


class CrawlKolRequest(BaseModel):
    kol_id: int
    max_count: int = Field(default=20, ge=1, le=100)


class CrawlSearchRequest(BaseModel):
    platform: str = Field(..., pattern="^(xhs|douyin|bilibili|weibo)$")
    keyword: str
    max_count: int = Field(default=20, ge=1, le=50)


class CrawlCommentsRequest(BaseModel):
    content_id: int
    max_count: int = Field(default=100, ge=1, le=500)


def _get_cookie(platform: str) -> str:
    cookie_map = {
        "xhs": settings.xhs_cookie,
        "douyin": settings.douyin_cookie,
        "bilibili": settings.bilibili_cookie,
        "weibo": settings.weibo_cookie,
    }
    return cookie_map.get(platform, "")


@router.post("/kol")
async def crawl_kol_contents(req: CrawlKolRequest):
    """手动抓取某个KOL的最新内容"""
    async with async_session() as db:
        kol = await db.get(KOL, req.kol_id)
        if not kol:
            raise HTTPException(404, "KOL不存在")

        logger.info(f"开始抓取KOL: {kol.name} ({kol.platform})")

        try:
            crawler = CrawlerFactory.get_crawler(kol.platform)
            items = await crawler.fetch_user_posts(
                user_id=kol.platform_uid,
                cookie=_get_cookie(kol.platform),
                max_count=req.max_count,
            )
        except Exception as e:
            logger.error(f"爬虫调用失败: {e}")
            raise HTTPException(500, f"爬虫调用失败: {str(e)}")

        # 入库去重
        new_count = 0
        skipped = 0
        for item in items:
            existing = await db.execute(
                select(Content).where(
                    Content.platform == kol.platform,
                    Content.content_id == item["content_id"],
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
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
            new_count += 1

        await db.commit()
        msg = f"抓取完成: 获取{len(items)}条, 新增{new_count}条, 跳过{skipped}条重复"
        logger.info(msg)
        return {
            "message": msg,
            "total_fetched": len(items),
            "new_count": new_count,
            "skipped": skipped,
        }


@router.post("/search")
async def crawl_search(req: CrawlSearchRequest):
    """关键词搜索抓取"""
    logger.info(f"搜索抓取: [{req.platform}] {req.keyword}")

    try:
        crawler = CrawlerFactory.get_crawler(req.platform)
        items = await crawler.search_posts(
            keyword=req.keyword,
            cookie=_get_cookie(req.platform),
            max_count=req.max_count,
        )
    except Exception as e:
        logger.error(f"搜索爬虫失败: {e}")
        raise HTTPException(500, f"搜索失败: {str(e)}")

    return {
        "message": f"搜索完成: 找到{len(items)}条结果",
        "total": len(items),
        "items": [
            {
                "content_id": it.get("content_id", ""),
                "title": it.get("title", ""),
                "url": it.get("url", ""),
                "cover_url": it.get("cover_url", ""),
                "content_type": it.get("content_type", ""),
                "like_count": it.get("like_count", 0),
                "comment_count": it.get("comment_count", 0),
                "view_count": it.get("view_count", 0),
                "tags": it.get("tags", ""),
            }
            for it in items
        ],
    }


@router.post("/comments")
async def crawl_comments(req: CrawlCommentsRequest):
    """抓取某条内容的评论"""
    async with async_session() as db:
        content = await db.get(Content, req.content_id)
        if not content:
            raise HTTPException(404, "内容不存在")

        logger.info(f"抓取评论: {content.title[:30]}...")

        try:
            crawler = CrawlerFactory.get_crawler(content.platform)
            comments = await crawler.fetch_post_comments(
                post_id=content.content_id,
                cookie=_get_cookie(content.platform),
                max_count=req.max_count,
            )
        except Exception as e:
            logger.error(f"评论爬虫失败: {e}")
            raise HTTPException(500, f"评论抓取失败: {str(e)}")

        # 入库
        new_count = 0
        for c in comments:
            existing = await db.execute(
                select(Comment).where(
                    Comment.content_id == content.id,
                    Comment.comment_id == c["comment_id"],
                )
            )
            if existing.scalar_one_or_none():
                continue
            comment = Comment(
                content_id=content.id,
                comment_id=c["comment_id"],
                parent_comment_id=c.get("parent_comment_id", ""),
                user_name=c.get("user_name", ""),
                user_id=c.get("user_id", ""),
                text=c.get("text", ""),
                like_count=c.get("like_count", 0),
                published_at=c.get("published_at"),
            )
            db.add(comment)
            new_count += 1

        await db.commit()
        msg = f"评论抓取完成: 获取{len(comments)}条, 新增{new_count}条"
        logger.info(msg)
        return {"message": msg, "total_fetched": len(comments), "new_count": new_count}


@router.post("/profile")
async def crawl_kol_profile(req: CrawlKolRequest):
    """抓取并更新KOL资料（粉丝数、头像、简介）"""
    async with async_session() as db:
        kol = await db.get(KOL, req.kol_id)
        if not kol:
            raise HTTPException(404, "KOL不存在")

        try:
            crawler = CrawlerFactory.get_crawler(kol.platform)
            profile = await crawler.fetch_user_profile(
                user_id=kol.platform_uid,
                cookie=_get_cookie(kol.platform),
            )
        except Exception as e:
            raise HTTPException(500, f"资料获取失败: {str(e)}")

        if not profile:
            return {"message": "该平台暂不支持资料抓取", "updated": False}

        # 更新KOL信息
        if profile.get("name") and not kol.name.strip():
            kol.name = profile["name"]
        if profile.get("avatar_url"):
            kol.avatar_url = profile["avatar_url"]
        if profile.get("follower_count"):
            kol.follower_count = profile["follower_count"]
        if profile.get("description"):
            kol.description = profile["description"]

        await db.commit()
        return {
            "message": f"资料已更新: {kol.name}",
            "updated": True,
            "profile": profile,
        }


class SaveSearchItemRequest(BaseModel):
    """保存搜索结果到数据库"""
    platform: str
    content_id: str
    title: str = ""
    url: str = ""
    cover_url: str = ""
    content_type: str = "video"
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0
    tags: str = ""


@router.post("/save")
async def save_search_result(req: SaveSearchItemRequest):
    """保存搜索结果到内容库"""
    async with async_session() as db:
        # 检查重复
        existing = await db.execute(
            select(Content).where(
                Content.platform == req.platform,
                Content.content_id == req.content_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"message": "内容已存在", "saved": False}

        content = Content(
            kol_id=None,  # 搜索结果无关联KOL
            platform=req.platform,
            content_type=req.content_type,
            content_id=req.content_id,
            title=req.title,
            url=req.url,
            cover_url=req.cover_url,
            like_count=req.like_count,
            comment_count=req.comment_count,
            view_count=req.view_count,
            tags=req.tags,
        )
        db.add(content)
        await db.commit()
        return {"message": f"已保存: {req.title[:30]}", "saved": True}


class UrlExtractRequest(BaseModel):
    """通用URL抓取"""
    url: str = Field(..., description="视频/帖子URL（支持抖音/B站/YouTube/Twitter/Instagram/TikTok）")
    save: bool = Field(default=True, description="是否保存到内容库")
    kol_id: int = 0


class BatchUrlRequest(BaseModel):
    """批量URL抓取"""
    urls: list = Field(..., description="URL列表")
    save: bool = True
    kol_id: int = 0


@router.post("/url")
async def extract_by_url(req: UrlExtractRequest):
    """通用URL抓取 - 粘贴任何视频链接，自动提取元数据

    支持平台: 抖音/B站/YouTube/TikTok/Twitter/Instagram
    """
    from core.crawler.ytdlp_engine import ytdlp_engine

    logger.info(f"URL抓取: {req.url}")
    info = await ytdlp_engine.extract_video_info(req.url)
    if not info:
        return {"message": "抓取失败，请检查URL是否正确", "success": False}

    result = {
        "message": f"抓取成功: {info.get('title', '')[:40]}",
        "success": True,
        "data": info,
    }

    if req.save:
        async with async_session() as db:
            existing = await db.execute(
                select(Content).where(
                    Content.platform == info["platform"],
                    Content.content_id == info["content_id"],
                )
            )
            if existing.scalar_one_or_none():
                result["message"] += " (已存在，跳过保存)"
            else:
                content = Content(
                    kol_id=req.kol_id if req.kol_id > 0 else None,
                    platform=info["platform"],
                    content_type=info["content_type"],
                    content_id=info["content_id"],
                    title=info["title"],
                    description=info.get("description", ""),
                    url=info["url"],
                    cover_url=info.get("cover_url", ""),
                    media_urls=info.get("media_urls"),
                    tags=info.get("tags", ""),
                    like_count=info.get("like_count", 0),
                    comment_count=info.get("comment_count", 0),
                    share_count=info.get("share_count", 0),
                    view_count=info.get("view_count", 0),
                    published_at=info.get("published_at"),
                    raw_data=info.get("raw_data"),
                )
                db.add(content)
                await db.commit()
                result["message"] += " (已保存)"

    return result


@router.post("/batch-url")
async def extract_batch_urls(req: BatchUrlRequest):
    """批量URL抓取"""
    from core.crawler.ytdlp_engine import ytdlp_engine

    logger.info(f"批量URL抓取: {len(req.urls)}个")
    results = await ytdlp_engine.extract_batch(req.urls)

    saved = 0
    if req.save and results:
        async with async_session() as db:
            for info in results:
                existing = await db.execute(
                    select(Content).where(
                        Content.platform == info["platform"],
                        Content.content_id == info["content_id"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                content = Content(
                    kol_id=req.kol_id if req.kol_id > 0 else None,
                    platform=info["platform"],
                    content_type=info["content_type"],
                    content_id=info["content_id"],
                    title=info["title"],
                    description=info.get("description", ""),
                    url=info["url"],
                    cover_url=info.get("cover_url", ""),
                    media_urls=info.get("media_urls"),
                    tags=info.get("tags", ""),
                    like_count=info.get("like_count", 0),
                    comment_count=info.get("comment_count", 0),
                    share_count=info.get("share_count", 0),
                    view_count=info.get("view_count", 0),
                    published_at=info.get("published_at"),
                    raw_data=info.get("raw_data"),
                )
                db.add(content)
                saved += 1
            await db.commit()

    return {
        "message": f"批量抓取完成: {len(results)}成功, {saved}条已保存",
        "total": len(results),
        "saved": saved,
        "items": [{"title": r.get("title", "")[:40], "platform": r.get("platform"), "url": r.get("url")} for r in results],
    }
