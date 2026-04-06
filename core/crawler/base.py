"""爬虫基类 - 所有平台爬虫的抽象接口"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import get_logger
from config.settings import settings

logger = get_logger("crawler.base")


class BaseCrawler(ABC):
    """平台爬虫基类"""

    platform: str = ""

    def __init__(self):
        self.headers = {
            "User-Agent": settings.crawler_user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.proxy = settings.crawler_proxy or None

    def _get_client(self, cookie: str = "") -> httpx.AsyncClient:
        """获取HTTP客户端"""
        headers = {**self.headers}
        if cookie:
            headers["Cookie"] = cookie
        return httpx.AsyncClient(
            headers=headers,
            proxy=self.proxy,
            timeout=30.0,
            follow_redirects=True,
        )

    async def fetch_user_profile(self, user_id: str, cookie: str = "") -> dict | None:
        """获取用户资料
        返回格式: {
            "name": str,
            "avatar_url": str,
            "follower_count": int,
            "following_count": int,
            "description": str,
            "video_count": int,
            "like_count": int,
        }
        默认返回None，子类可选实现
        """
        return None

    @abstractmethod
    async def fetch_user_posts(self, user_id: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """获取用户最新发布内容
        返回格式: [{
            "content_id": str,
            "content_type": str,  # video/article/note
            "title": str,
            "description": str,
            "url": str,
            "cover_url": str,
            "media_urls": list,
            "tags": str,
            "like_count": int,
            "comment_count": int,
            "share_count": int,
            "view_count": int,
            "published_at": datetime | None,
            "raw_data": dict,
        }]
        """
        ...

    @abstractmethod
    async def fetch_post_detail(self, post_id: str, cookie: str = "") -> dict | None:
        """获取单个内容详情"""
        ...

    @abstractmethod
    async def fetch_post_comments(self, post_id: str, cookie: str = "", max_count: int = 100) -> list[dict]:
        """获取内容评论
        返回格式: [{
            "comment_id": str,
            "parent_comment_id": str,
            "user_name": str,
            "user_id": str,
            "text": str,
            "like_count": int,
            "published_at": datetime | None,
        }]
        """
        ...

    @abstractmethod
    async def search_posts(self, keyword: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """关键词搜索内容"""
        ...

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _request(self, client: httpx.AsyncClient, method: str, url: str, **kwargs) -> Any:
        """带重试的HTTP请求"""
        resp = await client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _parse_timestamp(self, ts: int | float | str | None) -> datetime | None:
        """解析时间戳"""
        if not ts:
            return None
        try:
            if isinstance(ts, str):
                ts = int(ts)
            if ts > 1e12:  # 毫秒
                ts = ts / 1000
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            return None
