"""yt-dlp抓取引擎 - 真正能工作的跨平台数据抓取

yt-dlp能拿到视频元数据（标题/描述/播放量/点赞/评论数/封面/上传者等），
无需反爬签名，支持: 抖音单视频/B站/YouTube/TikTok/Twitter/Instagram

Twitter/Instagram 降级方案: 通过外部 media-downloader API 获取媒体
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Optional

import httpx

from config.settings import settings
from core.logger import get_logger

logger = get_logger("crawler.ytdlp")


class YtdlpEngine:
    """基于yt-dlp的元数据抓取引擎，Twitter/Instagram降级到外部API"""

    async def extract_video_info(self, url: str) -> dict | None:
        """提取单个视频/帖子的元数据"""
        # 先尝试 yt-dlp
        result = await self._ytdlp_extract(url)
        if result:
            return result

        # yt-dlp 失败时，Twitter/Instagram 走外部 media-downloader API
        if self._is_twitter_or_instagram(url):
            logger.info(f"yt-dlp失败，尝试外部API: {url}")
            return await self._media_downloader_extract(url)

        return None

    async def _ytdlp_extract(self, url: str) -> dict | None:
        """yt-dlp 提取"""
        try:
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                "--no-check-certificates",
                url,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                err = stderr.decode().strip()
                logger.warning(f"yt-dlp提取失败 [{url}]: {err[:200]}")
                return None

            data = json.loads(stdout.decode())
            return self._normalize(data, url)

        except json.JSONDecodeError as e:
            logger.error(f"yt-dlp输出解析失败: {e}")
            return None
        except FileNotFoundError:
            logger.error("yt-dlp未安装，请运行: pip install yt-dlp 或 brew install yt-dlp")
            return None
        except Exception as e:
            logger.error(f"yt-dlp异常: {e}")
            return None

    async def _media_downloader_extract(self, url: str) -> dict | None:
        """通过外部 media-downloader API 提取（Twitter/Instagram降级方案）"""
        api_base = settings.media_downloader_url.rstrip("/")
        if not api_base:
            return None

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # 提交任务
                resp = await client.post(f"{api_base}/api/download", json={"url": url})
                resp.raise_for_status()
                task_id = resp.json().get("task_id")
                if not task_id:
                    return None

                # 轮询等待结果（最多45秒）
                for _ in range(15):
                    await asyncio.sleep(3)
                    status_resp = await client.get(f"{api_base}/api/status/{task_id}")
                    status_data = status_resp.json()

                    if status_data.get("status") == "completed":
                        return self._normalize_downloader_result(status_data, url)
                    elif status_data.get("status") == "error":
                        err = status_data.get("result", {}).get("error", "unknown")
                        logger.warning(f"外部API失败 [{url}]: {err[:200]}")
                        return None

                logger.warning(f"外部API超时 [{url}]")
                return None

        except Exception as e:
            logger.error(f"外部API异常: {e}")
            return None

    def _normalize_downloader_result(self, data: dict, source_url: str) -> dict | None:
        """将 media-downloader API 的结果转为统一格式"""
        result = data.get("result", {})
        if not result.get("success"):
            return None

        files = result.get("files", [])
        platform = self._detect_platform("", source_url)

        # 从URL提取内容ID
        content_id = self._extract_id_from_url(source_url) or data.get("id", "")

        media_urls = []
        cover_url = ""
        for f in files:
            ftype = f.get("type", "video")
            furl = f.get("url", "")
            if ftype == "image" and not cover_url:
                cover_url = furl
            media_urls.append({"type": ftype, "url": furl})

        return {
            "content_id": str(content_id),
            "content_type": "video" if any(f.get("type") == "video" for f in files) else "note",
            "title": result.get("title", ""),
            "description": result.get("description", ""),
            "url": source_url,
            "cover_url": cover_url or result.get("thumbnail", ""),
            "media_urls": media_urls,
            "tags": "",
            "like_count": result.get("like_count", 0),
            "comment_count": result.get("comment_count", 0),
            "share_count": result.get("repost_count", 0),
            "view_count": result.get("view_count", 0),
            "published_at": None,
            "platform": platform,
            "uploader": result.get("author", ""),
            "uploader_id": result.get("author_id", ""),
            "duration": 0,
            "raw_data": {"source": "media-downloader-api", "task_id": data.get("id")},
        }

    @staticmethod
    def _is_twitter_or_instagram(url: str) -> bool:
        url_lower = url.lower()
        return any(d in url_lower for d in ["twitter.com", "x.com", "instagram.com"])

    @staticmethod
    def _extract_id_from_url(url: str) -> str:
        """从Twitter/Instagram URL中提取内容ID"""
        # Twitter: /status/1234567890
        m = re.search(r"/status/(\d+)", url)
        if m:
            return m.group(1)
        # Instagram: /p/ABC123/ or /reel/ABC123/
        m = re.search(r"/(p|reel|tv)/([A-Za-z0-9_-]+)", url)
        if m:
            return m.group(2)
        return ""

    async def extract_playlist(self, url: str, max_count: int = 20) -> list[dict]:
        """提取播放列表/用户主页的视频列表（B站空间、YouTube频道等）"""
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                "--no-check-certificates",
                "--playlist-end", str(max_count),
                url,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                err = stderr.decode().strip()
                logger.warning(f"yt-dlp列表提取失败 [{url}]: {err[:200]}")
                return []

            results = []
            for line in stdout.decode().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    normalized = self._normalize(data, url)
                    if normalized:
                        results.append(normalized)
                except json.JSONDecodeError:
                    continue

            logger.info(f"yt-dlp列表提取完成: {len(results)}条 [{url}]")
            return results

        except FileNotFoundError:
            logger.error("yt-dlp未安装")
            return []
        except Exception as e:
            logger.error(f"yt-dlp列表异常: {e}")
            return []

    async def extract_batch(self, urls: list[str]) -> list[dict]:
        """批量提取多个URL的元数据"""
        tasks = [self.extract_video_info(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    def _normalize(self, data: dict, source_url: str = "") -> dict | None:
        """将yt-dlp输出标准化为统一格式"""
        if not data:
            return None

        # 识别平台
        extractor = (data.get("extractor_key") or data.get("ie_key") or "").lower()
        platform = self._detect_platform(extractor, source_url)

        # 构建视频URL
        video_url = data.get("webpage_url") or data.get("url") or source_url
        video_id = data.get("id") or data.get("display_id") or ""

        # 封面
        thumbnail = data.get("thumbnail") or ""
        if not thumbnail:
            thumbs = data.get("thumbnails") or []
            if thumbs:
                thumbnail = thumbs[-1].get("url", "")

        # 时间
        published_at = None
        ts = data.get("timestamp")
        if ts:
            try:
                published_at = datetime.fromtimestamp(int(ts))
            except (ValueError, OSError):
                pass
        if not published_at and data.get("upload_date"):
            try:
                published_at = datetime.strptime(data["upload_date"], "%Y%m%d")
            except ValueError:
                pass

        # 标签
        tags_list = data.get("tags") or []
        tags = ",".join(str(t) for t in tags_list[:10]) if tags_list else ""

        return {
            "content_id": str(video_id),
            "content_type": self._detect_type(data),
            "title": data.get("title") or data.get("fulltitle") or "",
            "description": data.get("description") or "",
            "url": video_url,
            "cover_url": thumbnail,
            "media_urls": [{"type": "video", "url": video_url}],
            "tags": tags,
            "like_count": data.get("like_count") or 0,
            "comment_count": data.get("comment_count") or 0,
            "share_count": data.get("repost_count") or 0,
            "view_count": data.get("view_count") or 0,
            "published_at": published_at,
            "platform": platform,
            "uploader": data.get("uploader") or data.get("channel") or "",
            "uploader_id": data.get("uploader_id") or data.get("channel_id") or "",
            "duration": data.get("duration") or 0,
            "raw_data": {
                k: data.get(k)
                for k in ["title", "description", "view_count", "like_count",
                           "comment_count", "uploader", "upload_date", "duration",
                           "extractor_key", "id"]
                if data.get(k) is not None
            },
        }

    def _detect_platform(self, extractor: str, url: str = "") -> str:
        """根据extractor或URL识别平台"""
        mapping = {
            "bilibili": "bilibili",
            "bilibilispace": "bilibili",
            "douyin": "douyin",
            "tiktok": "tiktok",
            "twitter": "twitter",
            "youtube": "youtube",
            "instagram": "instagram",
            "weibo": "weibo",
            "xiaohongshu": "xhs",
        }
        for key, plat in mapping.items():
            if key in extractor:
                return plat

        # fallback: 从URL判断
        url_lower = url.lower()
        if "bilibili.com" in url_lower:
            return "bilibili"
        if "douyin.com" in url_lower:
            return "douyin"
        if "tiktok.com" in url_lower:
            return "tiktok"
        if "twitter.com" in url_lower or "x.com" in url_lower:
            return "twitter"
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        if "instagram.com" in url_lower:
            return "instagram"
        if "weibo.com" in url_lower:
            return "weibo"
        if "xiaohongshu.com" in url_lower:
            return "xhs"

        return "other"

    def _detect_type(self, data: dict) -> str:
        """判断内容类型"""
        duration = data.get("duration") or 0
        if duration > 0:
            if duration <= 60:
                return "short_video"
            return "video"
        return "video"


# 全局单例
ytdlp_engine = YtdlpEngine()
