"""媒体下载引擎 - 对接已有下载器 + yt-dlp本地兜底"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from config.settings import settings
from core.logger import get_logger

logger = get_logger("downloader")


class DownloadEngine:
    """统一媒体下载接口"""

    def __init__(self):
        self.remote_url = settings.media_downloader_url
        self.output_dir = settings.raw_dir / "media"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def download(self, url: str, platform: str = "", filename: str = "") -> dict:
        """下载媒体文件
        优先使用远程下载器，失败后本地yt-dlp兜底
        """
        # 先尝试远程下载器
        result = await self._remote_download(url)
        if result and result.get("success"):
            return result

        # 本地yt-dlp兜底
        logger.info(f"远程下载器失败，使用本地yt-dlp: {url}")
        return await self._local_download(url, filename)

    async def _remote_download(self, url: str) -> dict | None:
        """调用远程媒体下载器API"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 提交下载任务
                resp = await client.post(
                    f"{self.remote_url}/api/download",
                    json={"url": url, "quality": "1080p"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"远程下载成功: {url}")
                    return {"success": True, "source": "remote", "data": data}
        except Exception as e:
            logger.warning(f"远程下载器调用失败: {e}")
        return None

    async def _local_download(self, url: str, filename: str = "") -> dict:
        """本地yt-dlp下载"""
        try:
            output_template = str(self.output_dir / (filename or "%(title)s.%(ext)s"))
            cmd = [
                "yt-dlp",
                "--no-warnings",
                "-o", output_template,
                "--write-thumbnail",
                "--write-info-json",
                url,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"本地下载成功: {url}")
                return {
                    "success": True,
                    "source": "local",
                    "output": stdout.decode(),
                    "output_dir": str(self.output_dir),
                }
            else:
                error_msg = stderr.decode()
                logger.error(f"本地下载失败: {error_msg}")
                return {"success": False, "error": error_msg}
        except FileNotFoundError:
            logger.error("yt-dlp未安装，请运行: pip install yt-dlp")
            return {"success": False, "error": "yt-dlp未安装"}
        except Exception as e:
            logger.error(f"本地下载异常: {e}")
            return {"success": False, "error": str(e)}

    async def batch_download(self, urls: list[str]) -> list[dict]:
        """批量下载"""
        tasks = [self.download(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)


download_engine = DownloadEngine()
