"""B站爬虫 - 基于公开API"""

from core.crawler.base import BaseCrawler
from core.logger import get_logger

logger = get_logger("crawler.bilibili")

BILI_API = "https://api.bilibili.com"


class BilibiliCrawler(BaseCrawler):
    platform = "bilibili"

    def __init__(self):
        super().__init__()
        self.headers.update({
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        })

    async def fetch_user_posts(self, user_id: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """获取B站UP主视频列表"""
        url = f"{BILI_API}/x/space/wbi/arc/search"
        params = {
            "mid": user_id,
            "ps": min(max_count, 30),
            "pn": 1,
            "order": "pubdate",
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                vlist = data.get("data", {}).get("list", {}).get("vlist", [])
                return [self._parse_video(v) for v in vlist]
            except Exception as e:
                logger.error(f"获取B站UP主 {user_id} 视频失败: {e}")
                return []

    async def fetch_post_detail(self, post_id: str, cookie: str = "") -> dict | None:
        """获取B站视频详情"""
        url = f"{BILI_API}/x/web-interface/view"
        params = {"bvid": post_id} if post_id.startswith("BV") else {"aid": post_id}

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                video = data.get("data")
                if video:
                    return self._parse_video_detail(video)
                return None
            except Exception as e:
                logger.error(f"获取B站视频详情 {post_id} 失败: {e}")
                return None

    async def fetch_post_comments(self, post_id: str, cookie: str = "", max_count: int = 100) -> list[dict]:
        """获取B站视频评论"""
        # 先获取aid
        if post_id.startswith("BV"):
            detail = await self.fetch_post_detail(post_id, cookie)
            if not detail:
                return []
            oid = detail.get("raw_data", {}).get("aid", "")
        else:
            oid = post_id

        url = f"{BILI_API}/x/v2/reply"
        comments = []
        pn = 1

        async with self._get_client(cookie) as client:
            while len(comments) < max_count:
                params = {"type": 1, "oid": oid, "pn": pn, "ps": 20, "sort": 1}
                try:
                    data = await self._request(client, "GET", url, params=params)
                    replies = data.get("data", {}).get("replies") or []
                    if not replies:
                        break
                    for reply in replies:
                        comments.append(self._parse_comment(reply))
                        for sub in (reply.get("replies") or []):
                            comments.append(self._parse_comment(sub, parent_id=str(reply.get("rpid", ""))))
                    pn += 1
                except Exception as e:
                    logger.error(f"获取B站评论失败: {e}")
                    break

        return comments[:max_count]

    async def search_posts(self, keyword: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """B站关键词搜索"""
        url = f"{BILI_API}/x/web-interface/search/type"
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": 1,
            "pagesize": min(max_count, 20),
            "order": "totalrank",
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                results = data.get("data", {}).get("result", [])
                return [self._parse_search_result(r) for r in results]
            except Exception as e:
                logger.error(f"B站搜索 '{keyword}' 失败: {e}")
                return []

    def _parse_video(self, v: dict) -> dict:
        """解析空间视频列表项"""
        return {
            "content_id": v.get("bvid", ""),
            "content_type": "video",
            "title": v.get("title", ""),
            "description": v.get("description", ""),
            "url": f"https://www.bilibili.com/video/{v.get('bvid', '')}",
            "cover_url": v.get("pic", ""),
            "media_urls": None,
            "tags": "",
            "like_count": 0,
            "comment_count": v.get("comment", 0),
            "share_count": 0,
            "view_count": v.get("play", 0),
            "published_at": self._parse_timestamp(v.get("created")),
            "raw_data": v,
        }

    def _parse_video_detail(self, v: dict) -> dict:
        """解析视频详情"""
        stat = v.get("stat", {})
        tags = ",".join(t.get("tag_name", "") for t in v.get("tag", []) if t.get("tag_name"))
        return {
            "content_id": v.get("bvid", ""),
            "content_type": "video",
            "title": v.get("title", ""),
            "description": v.get("desc", ""),
            "url": f"https://www.bilibili.com/video/{v.get('bvid', '')}",
            "cover_url": v.get("pic", ""),
            "media_urls": None,
            "tags": tags,
            "like_count": stat.get("like", 0),
            "comment_count": stat.get("reply", 0),
            "share_count": stat.get("share", 0),
            "view_count": stat.get("view", 0),
            "published_at": self._parse_timestamp(v.get("pubdate")),
            "raw_data": v,
        }

    def _parse_search_result(self, r: dict) -> dict:
        """解析搜索结果"""
        return {
            "content_id": r.get("bvid", ""),
            "content_type": "video",
            "title": r.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
            "description": r.get("description", ""),
            "url": f"https://www.bilibili.com/video/{r.get('bvid', '')}",
            "cover_url": "https:" + r.get("pic", "") if r.get("pic") else "",
            "media_urls": None,
            "tags": r.get("tag", ""),
            "like_count": r.get("like", 0),
            "comment_count": r.get("review", 0),
            "share_count": 0,
            "view_count": r.get("play", 0),
            "published_at": self._parse_timestamp(r.get("pubdate")),
            "raw_data": r,
        }

    def _parse_comment(self, reply: dict, parent_id: str = "") -> dict:
        """解析评论"""
        member = reply.get("member", {})
        content = reply.get("content", {})
        return {
            "comment_id": str(reply.get("rpid", "")),
            "parent_comment_id": parent_id,
            "user_name": member.get("uname", ""),
            "user_id": str(member.get("mid", "")),
            "text": content.get("message", ""),
            "like_count": reply.get("like", 0),
            "published_at": self._parse_timestamp(reply.get("ctime")),
        }
