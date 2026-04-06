"""快手爬虫 - 基于GraphQL API"""

import json
from core.crawler.base import BaseCrawler
from core.logger import get_logger

logger = get_logger("crawler.kuaishou")

KS_GRAPHQL = "https://www.kuaishou.com/graphql"


class KuaishouCrawler(BaseCrawler):
    platform = "kuaishou"

    def __init__(self):
        super().__init__()
        self.headers.update({
            "Referer": "https://www.kuaishou.com/",
            "Origin": "https://www.kuaishou.com",
            "Content-Type": "application/json",
        })

    async def fetch_user_posts(self, user_id: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """获取快手用户视频列表"""
        query = {
            "operationName": "visionProfilePhotoList",
            "variables": {"userId": user_id, "pcursor": "", "page": "profile"},
            "query": """query visionProfilePhotoList($userId: String, $pcursor: String, $page: String) {
                visionProfilePhotoList(userId: $userId, pcursor: $pcursor, page: $page) {
                    result
                    llsid
                    webPageArea
                    feeds { photo { id caption likeCount viewCount commentCount timestamp coverUrl photoUrl animatedCoverUrl duration } }
                    hostName
                    pcursor
                }
            }""",
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "POST", KS_GRAPHQL, json=query)
                feeds = data.get("data", {}).get("visionProfilePhotoList", {}).get("feeds", [])
                return [self._parse_photo(f.get("photo", {})) for f in feeds[:max_count]]
            except Exception as e:
                logger.error(f"获取快手用户 {user_id} 视频失败: {e}")
                return []

    async def fetch_post_detail(self, post_id: str, cookie: str = "") -> dict | None:
        """获取快手视频详情"""
        query = {
            "operationName": "visionVideoDetail",
            "variables": {"photoId": post_id, "page": "detail"},
            "query": """query visionVideoDetail($photoId: String, $page: String) {
                visionVideoDetail(photoId: $photoId, page: $page) {
                    photo { id caption likeCount viewCount commentCount timestamp coverUrl photoUrl duration }
                }
            }""",
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "POST", KS_GRAPHQL, json=query)
                photo = data.get("data", {}).get("visionVideoDetail", {}).get("photo")
                if photo:
                    return self._parse_photo(photo)
                return None
            except Exception as e:
                logger.error(f"获取快手视频详情 {post_id} 失败: {e}")
                return None

    async def fetch_post_comments(self, post_id: str, cookie: str = "", max_count: int = 100) -> list[dict]:
        """获取快手视频评论"""
        query = {
            "operationName": "commentListQuery",
            "variables": {"photoId": post_id, "pcursor": ""},
            "query": """query commentListQuery($photoId: String, $pcursor: String) {
                visionCommentList(photoId: $photoId, pcursor: $pcursor) {
                    commentCount
                    pcursor
                    rootComments {
                        commentId content headurl userName likeCount timestamp
                        subComments { commentId content headurl userName likeCount timestamp replyTo }
                    }
                }
            }""",
        }

        comments = []
        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "POST", KS_GRAPHQL, json=query)
                root_comments = (
                    data.get("data", {}).get("visionCommentList", {}).get("rootComments", [])
                )
                for rc in root_comments:
                    comments.append({
                        "comment_id": rc.get("commentId", ""),
                        "parent_comment_id": "",
                        "user_name": rc.get("userName", ""),
                        "user_id": "",
                        "text": rc.get("content", ""),
                        "like_count": rc.get("likeCount", 0),
                        "published_at": self._parse_timestamp(rc.get("timestamp")),
                    })
                    for sub in (rc.get("subComments") or []):
                        comments.append({
                            "comment_id": sub.get("commentId", ""),
                            "parent_comment_id": rc.get("commentId", ""),
                            "user_name": sub.get("userName", ""),
                            "user_id": "",
                            "text": sub.get("content", ""),
                            "like_count": sub.get("likeCount", 0),
                            "published_at": self._parse_timestamp(sub.get("timestamp")),
                        })
            except Exception as e:
                logger.error(f"获取快手评论失败: {e}")

        return comments[:max_count]

    async def search_posts(self, keyword: str, cookie: str = "", max_count: int = 20) -> list[dict]:
        """快手关键词搜索"""
        query = {
            "operationName": "visionSearchPhoto",
            "variables": {"keyword": keyword, "pcursor": "", "page": "search"},
            "query": """query visionSearchPhoto($keyword: String, $pcursor: String, $page: String) {
                visionSearchPhoto(keyword: $keyword, pcursor: $pcursor, page: $page) {
                    feeds { photo { id caption likeCount viewCount commentCount timestamp coverUrl photoUrl duration } }
                    pcursor
                }
            }""",
        }

        async with self._get_client(cookie) as client:
            try:
                data = await self._request(client, "POST", KS_GRAPHQL, json=query)
                feeds = data.get("data", {}).get("visionSearchPhoto", {}).get("feeds", [])
                return [self._parse_photo(f.get("photo", {})) for f in feeds[:max_count]]
            except Exception as e:
                logger.error(f"快手搜索 '{keyword}' 失败: {e}")
                return []

    def _parse_photo(self, photo: dict) -> dict:
        """解析快手视频数据"""
        photo_id = str(photo.get("id", ""))
        return {
            "content_id": photo_id,
            "content_type": "short_video",
            "title": photo.get("caption", ""),
            "description": photo.get("caption", ""),
            "url": f"https://www.kuaishou.com/short-video/{photo_id}",
            "cover_url": photo.get("coverUrl", ""),
            "media_urls": [{"type": "video", "url": photo.get("photoUrl", "")}] if photo.get("photoUrl") else None,
            "tags": "",
            "like_count": photo.get("likeCount", 0),
            "comment_count": photo.get("commentCount", 0),
            "share_count": 0,
            "view_count": photo.get("viewCount", 0),
            "published_at": self._parse_timestamp(photo.get("timestamp")),
            "raw_data": photo,
        }
