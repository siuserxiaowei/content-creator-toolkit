"""抖音爬虫 - 基于Web API"""

from core.crawler.base import BaseCrawler
from core.logger import get_logger

logger = get_logger("crawler.douyin")

DOUYIN_API_BASE = "https://www.douyin.com/aweme/v1/web"


class DouyinCrawler(BaseCrawler):
    platform = "douyin"

    def __init__(self):
        super().__init__()
        self.headers.update({
            "Referer": "https://www.douyin.com/",
            "Origin": "https://www.douyin.com",
        })

    async def fetch_user_posts(self, user_id: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """获取抖音用户视频列表"""
        url = f"{DOUYIN_API_BASE}/aweme/post/"
        params = {
            "sec_user_id": user_id,
            "count": min(max_count, 20),
            "max_cursor": 0,
            "aid": 6383,
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                aweme_list = data.get("aweme_list", [])
                return [self._parse_aweme(a) for a in aweme_list]
            except Exception as e:
                logger.error(f"获取抖音用户 {user_id} 视频失败: {e}")
                return []

    async def fetch_post_detail(self, post_id: str, cookie: str = "") -> dict | None:
        """获取抖音视频详情"""
        url = f"{DOUYIN_API_BASE}/aweme/detail/"
        params = {"aweme_id": post_id, "aid": 6383}

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                aweme = data.get("aweme_detail")
                if aweme:
                    return self._parse_aweme(aweme)
                return None
            except Exception as e:
                logger.error(f"获取抖音视频详情 {post_id} 失败: {e}")
                return None

    async def fetch_post_comments(self, post_id: str, cookie: str = "", max_count: int = 100) -> list[dict]:
        """获取抖音视频评论"""
        url = f"{DOUYIN_API_BASE}/comment/list/"
        comments = []
        cursor = 0

        async with self._get_client(cookie) as client:
            while len(comments) < max_count:
                params = {
                    "aweme_id": post_id,
                    "cursor": cursor,
                    "count": 20,
                    "aid": 6383,
                }
                try:
                    data = await self._request(client, "GET", url, params=params)
                    items = data.get("comments", [])
                    if not items:
                        break
                    for item in items:
                        comments.append(self._parse_comment(item))
                    if not data.get("has_more", False):
                        break
                    cursor = data.get("cursor", 0)
                except Exception as e:
                    logger.error(f"获取抖音评论失败: {e}")
                    break

        return comments[:max_count]

    async def search_posts(self, keyword: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """抖音关键词搜索"""
        url = f"{DOUYIN_API_BASE}/general/search/single/"
        params = {
            "keyword": keyword,
            "search_channel": "aweme_general",
            "count": min(max_count, 20),
            "offset": 0,
            "aid": 6383,
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                items = data.get("data", [])
                results = []
                for item in items:
                    aweme = item.get("aweme_info")
                    if aweme:
                        results.append(self._parse_aweme(aweme))
                return results
            except Exception as e:
                logger.error(f"抖音搜索 '{keyword}' 失败: {e}")
                return []

    def _parse_aweme(self, aweme: dict) -> dict:
        """解析抖音视频数据"""
        stats = aweme.get("statistics", {})
        video = aweme.get("video", {})
        play_addr = video.get("play_addr", {})

        media_urls = []
        if play_addr.get("url_list"):
            media_urls.append({"type": "video", "url": play_addr["url_list"][0]})
        cover = video.get("cover", {})
        if cover.get("url_list"):
            media_urls.append({"type": "cover", "url": cover["url_list"][0]})

        # 话题标签
        text_extra = aweme.get("text_extra", [])
        tags = ",".join(t.get("hashtag_name", "") for t in text_extra if t.get("hashtag_name"))

        return {
            "content_id": str(aweme.get("aweme_id", "")),
            "content_type": "short_video",
            "title": aweme.get("desc", ""),
            "description": aweme.get("desc", ""),
            "url": f"https://www.douyin.com/video/{aweme.get('aweme_id', '')}",
            "cover_url": cover.get("url_list", [""])[0] if cover.get("url_list") else "",
            "media_urls": media_urls,
            "tags": tags,
            "like_count": stats.get("digg_count", 0),
            "comment_count": stats.get("comment_count", 0),
            "share_count": stats.get("share_count", 0),
            "view_count": stats.get("play_count", 0),
            "published_at": self._parse_timestamp(aweme.get("create_time")),
            "raw_data": aweme,
        }

    def _parse_comment(self, comment: dict) -> dict:
        """解析评论"""
        user = comment.get("user", {})
        return {
            "comment_id": str(comment.get("cid", "")),
            "parent_comment_id": str(comment.get("reply_id", "")) if comment.get("reply_id") else "",
            "user_name": user.get("nickname", ""),
            "user_id": str(user.get("uid", "")),
            "text": comment.get("text", ""),
            "like_count": comment.get("digg_count", 0),
            "published_at": self._parse_timestamp(comment.get("create_time")),
        }
