"""小红书爬虫 - 基于Web API"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from core.crawler.base import BaseCrawler
from core.logger import get_logger

logger = get_logger("crawler.xhs")

# 小红书Web API基础URL
XHS_API_BASE = "https://edith.xiaohongshu.com/api/sns"


class XHSCrawler(BaseCrawler):
    platform = "xhs"

    def __init__(self):
        super().__init__()
        self.headers.update({
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/",
        })

    async def fetch_user_posts(self, user_id: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """获取小红书用户笔记列表"""
        url = f"{XHS_API_BASE}/web/v1/user_posted"
        params = {
            "num": min(max_count, 30),
            "cursor": "",
            "user_id": user_id,
            "image_formats": "jpg,webp,avif",
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "GET", url, params=params)
                notes = data.get("data", {}).get("notes", [])
                return [self._parse_note(note) for note in notes]
            except Exception as e:
                logger.error(f"获取小红书用户 {user_id} 笔记失败: {e}")
                return []

    async def fetch_post_detail(self, post_id: str, cookie: str = "") -> dict | None:
        """获取小红书笔记详情"""
        url = f"{XHS_API_BASE}/web/v1/feed"
        payload = {"source_note_id": post_id, "image_formats": ["jpg", "webp", "avif"]}

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "POST", url, json=payload)
                items = data.get("data", {}).get("items", [])
                if items:
                    note_card = items[0].get("note_card", {})
                    return self._parse_note_detail(note_card, post_id)
                return None
            except Exception as e:
                logger.error(f"获取小红书笔记详情 {post_id} 失败: {e}")
                return None

    async def fetch_post_comments(self, post_id: str, cookie: str = "", max_count: int = 100) -> list[dict]:
        """获取小红书笔记评论"""
        url = f"{XHS_API_BASE}/web/v2/comment/page"
        comments = []
        cursor = ""

        async with self._get_client(cookie) as client:
            while len(comments) < max_count:
                params = {
                    "note_id": post_id,
                    "cursor": cursor,
                    "top_comment_id": "",
                    "image_formats": "jpg,webp,avif",
                }
                try:
                    data = await self._request(client, "GET", url, params=params)
                    items = data.get("data", {}).get("comments", [])
                    if not items:
                        break
                    for item in items:
                        comments.append(self._parse_comment(item))
                        # 子评论
                        for sub in item.get("sub_comments", []):
                            comments.append(self._parse_comment(sub, parent_id=item.get("id", "")))
                    cursor = data.get("data", {}).get("cursor", "")
                    if not data.get("data", {}).get("has_more", False):
                        break
                except Exception as e:
                    logger.error(f"获取小红书评论失败: {e}")
                    break

        return comments[:max_count]

    async def search_posts(self, keyword: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """小红书关键词搜索"""
        url = f"{XHS_API_BASE}/web/v1/search/notes"
        payload = {
            "keyword": keyword,
            "page": 1,
            "page_size": min(max_count, 20),
            "search_id": "",
            "sort": "general",
            "note_type": 0,  # 0=全部, 1=视频, 2=图文
            "image_formats": ["jpg", "webp", "avif"],
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "POST", url, json=payload)
                items = data.get("data", {}).get("items", [])
                return [self._parse_search_note(item) for item in items if item.get("model_type") == "note"]
            except Exception as e:
                logger.error(f"小红书搜索 '{keyword}' 失败: {e}")
                return []

    def _parse_note(self, note: dict) -> dict:
        """解析笔记列表项"""
        interact = note.get("interact_info", {})
        return {
            "content_id": note.get("note_id", ""),
            "content_type": "video" if note.get("type") == "video" else "note",
            "title": note.get("display_title", ""),
            "description": "",
            "url": f"https://www.xiaohongshu.com/explore/{note.get('note_id', '')}",
            "cover_url": note.get("cover", {}).get("url_default", ""),
            "media_urls": None,
            "tags": "",
            "like_count": int(interact.get("liked_count", "0") or 0),
            "comment_count": 0,
            "share_count": 0,
            "view_count": 0,
            "published_at": self._parse_timestamp(note.get("time")),
            "raw_data": note,
        }

    def _parse_note_detail(self, note: dict, note_id: str) -> dict:
        """解析笔记详情"""
        interact = note.get("interact_info", {})
        image_list = note.get("image_list", [])
        video = note.get("video", {})

        media_urls = []
        if video:
            media_urls.append({"type": "video", "url": video.get("consumer", {}).get("origin_video_key", "")})
        for img in image_list:
            media_urls.append({"type": "image", "url": img.get("url_default", "")})

        tag_list = note.get("tag_list", [])
        tags = ",".join(t.get("name", "") for t in tag_list)

        return {
            "content_id": note_id,
            "content_type": "video" if video else "note",
            "title": note.get("title", ""),
            "description": note.get("desc", ""),
            "url": f"https://www.xiaohongshu.com/explore/{note_id}",
            "cover_url": note.get("image_list", [{}])[0].get("url_default", "") if image_list else "",
            "media_urls": media_urls,
            "tags": tags,
            "like_count": int(interact.get("liked_count", "0") or 0),
            "comment_count": int(interact.get("comment_count", "0") or 0),
            "share_count": int(interact.get("share_count", "0") or 0),
            "view_count": 0,
            "published_at": self._parse_timestamp(note.get("time")),
            "raw_data": note,
        }

    def _parse_search_note(self, item: dict) -> dict:
        """解析搜索结果项"""
        note = item.get("note_card", {})
        return self._parse_note_detail(note, item.get("id", ""))

    def _parse_comment(self, comment: dict, parent_id: str = "") -> dict:
        """解析评论"""
        user = comment.get("user_info", {})
        return {
            "comment_id": comment.get("id", ""),
            "parent_comment_id": parent_id,
            "user_name": user.get("nickname", ""),
            "user_id": user.get("user_id", ""),
            "text": comment.get("content", ""),
            "like_count": int(comment.get("like_count", "0") or 0),
            "published_at": self._parse_timestamp(comment.get("create_time")),
        }
