"""yt-dlp抓取引擎 - 真正能工作的跨平台数据抓取

yt-dlp能拿到视频元数据（标题/描述/播放量/点赞/评论数/封面/上传者等），
无需反爬签名，支持: 抖音单视频/B站/YouTube/TikTok/Twitter/Instagram
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from core.logger import get_logger

logger = get_logger("crawler.ytdlp")


class YtdlpEngine:
    """基于yt-dlp的元数据抓取引擎"""

    async def extract_video_info(self, url: str) -> dict | None:
        """提取单个视频/帖子的元数据"""
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
