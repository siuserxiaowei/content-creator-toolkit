"""微博爬虫 - 基于移动端API"""
from __future__ import annotations

from core.crawler.base import BaseCrawler
from core.logger import get_logger

logger = get_logger("crawler.weibo")

WEIBO_API = "https://m.weibo.cn/api"


class WeiboCrawler(BaseCrawler):
    platform = "weibo"

    def __init__(self):
        super().__init__()
        self.headers.update({
            "Referer": "https://m.weibo.cn/",
            "X-Requested-With": "XMLHttpRequest",
        })

    async def fetch_user_profile(self, user_id: str, cookie: str = "") -> dict | None:
        """获取微博用户资料"""
        url = f"{WEIBO_API}/container/getIndex"
        params = {"type": "uid", "value": user_id}
        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                info = data.get("data", {}).get("userInfo", {})
                if info:
                    return {
                        "name": info.get("screen_name", ""),
                        "avatar_url": info.get("avatar_hd", ""),
                        "follower_count": info.get("followers_count", 0),
                        "following_count": info.get("follow_count", 0),
                        "description": info.get("description", ""),
                        "video_count": info.get("statuses_count", 0),
                        "like_count": 0,
                    }
                return None
            except Exception as e:
                logger.warning(f"获取微博用户资料失败: {e}")
                return None

    async def fetch_user_posts(self, user_id: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """获取微博用户最新微博"""
        url = f"{WEIBO_API}/container/getIndex"
        # containerid格式: 107603+uid
        params = {"type": "uid", "value": user_id, "containerid": f"107603{user_id}", "page": 1}

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                cards = data.get("data", {}).get("cards", [])
                results = []
                for card in cards:
                    if card.get("card_type") == 9:
                        mblog = card.get("mblog", {})
                        if mblog:
                            results.append(self._parse_mblog(mblog))
                return results[:max_count]
            except Exception as e:
                logger.error(f"获取微博用户 {user_id} 微博失败: {e}")
                return []

    async def fetch_post_detail(self, post_id: str, cookie: str = "") -> dict | None:
        """获取微博详情"""
        url = f"{WEIBO_API}/statuses/show"
        params = {"id": post_id}

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                mblog = data.get("data")
                if mblog:
                    return self._parse_mblog(mblog)
                return None
            except Exception as e:
                logger.error(f"获取微博详情 {post_id} 失败: {e}")
                return None

    async def fetch_post_comments(self, post_id: str, cookie: str = "", max_count: int = 100) -> list[dict]:
        """获取微博评论"""
        url = f"{WEIBO_API}/comments/hotflow"
        comments = []
        max_id = 0

        async with self._get_client(cookie) as client:
            while len(comments) < max_count:
                params = {"id": post_id, "mid": post_id, "max_id": max_id, "max_id_type": 0}
                try:
                    data = await self._request(client, "GET", url, params=params)
                    items = data.get("data", {}).get("data", [])
                    if not items:
                        break
                    for item in items:
                        comments.append(self._parse_comment(item))
                    max_id = data.get("data", {}).get("max_id", 0)
                    if not max_id:
                        break
                except Exception as e:
                    logger.error(f"获取微博评论失败: {e}")
                    break

        return comments[:max_count]

    async def search_posts(self, keyword: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """微博关键词搜索"""
        url = f"{WEIBO_API}/container/getIndex"
        params = {"containerid": f"100103type=1&q={keyword}", "page_type": "searchall", "page": 1}

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                cards = data.get("data", {}).get("cards", [])
                results = []
                for card in cards:
                    card_group = card.get("card_group", [])
                    for item in card_group:
                        mblog = item.get("mblog")
                        if mblog:
                            results.append(self._parse_mblog(mblog))
                return results[:max_count]
            except Exception as e:
                logger.error(f"微博搜索 '{keyword}' 失败: {e}")
                return []

    def _parse_mblog(self, mblog: dict) -> dict:
        """解析微博数据"""
        # 提取媒体URL
        media_urls = []
        pics = mblog.get("pics", [])
        for pic in pics:
            media_urls.append({"type": "image", "url": pic.get("large", {}).get("url", "")})

        page_info = mblog.get("page_info", {})
        if page_info.get("type") == "video":
            video_url = page_info.get("urls", {})
            if video_url:
                best = video_url.get("mp4_720p_mp4") or video_url.get("mp4_hd_mp4") or ""
                if best:
                    media_urls.append({"type": "video", "url": best})

        mid = str(mblog.get("mid", "") or mblog.get("id", ""))
        content_type = "video" if page_info.get("type") == "video" else "article"

        return {
            "content_id": mid,
            "content_type": content_type,
            "title": mblog.get("text", "")[:100],
            "description": mblog.get("text", ""),
            "url": f"https://m.weibo.cn/detail/{mid}",
            "cover_url": page_info.get("page_pic", {}).get("url", "") if page_info else "",
            "media_urls": media_urls if media_urls else None,
            "tags": "",
            "like_count": mblog.get("attitudes_count", 0),
            "comment_count": mblog.get("comments_count", 0),
            "share_count": mblog.get("reposts_count", 0),
            "view_count": 0,
            "published_at": None,  # 微博时间格式复杂，后续处理
            "raw_data": mblog,
        }

    def _parse_comment(self, comment: dict) -> dict:
        """解析评论"""
        user = comment.get("user", {})
        return {
            "comment_id": str(comment.get("id", "")),
            "parent_comment_id": "",
            "user_name": user.get("screen_name", ""),
            "user_id": str(user.get("id", "")),
            "text": comment.get("text", ""),
            "like_count": comment.get("like_count", 0),
            "published_at": None,
        }
