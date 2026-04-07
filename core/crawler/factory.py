"""爬虫工厂 - 根据平台返回对应爬虫实例"""

from core.crawler.base import BaseCrawler
from core.crawler.xhs import XHSCrawler
from core.crawler.douyin import DouyinCrawler
from core.crawler.bilibili import BilibiliCrawler
from core.crawler.weibo import WeiboCrawler


class CrawlerFactory:
    """爬虫工厂"""

    _crawlers: dict[str, BaseCrawler] = {}

    @classmethod
    def get_crawler(cls, platform: str) -> BaseCrawler:
        """获取平台爬虫实例（单例）"""
        if platform not in cls._crawlers:
            crawler_map = {
                "xhs": XHSCrawler,
                "douyin": DouyinCrawler,
                "bilibili": BilibiliCrawler,
                "weibo": WeiboCrawler,
            }
            crawler_cls = crawler_map.get(platform)
            if not crawler_cls:
                raise ValueError(f"不支持的平台: {platform}，支持: {list(crawler_map.keys())}")
            cls._crawlers[platform] = crawler_cls()
        return cls._crawlers[platform]

    @classmethod
    def supported_platforms(cls) -> list[str]:
        return ["xhs", "douyin", "bilibili", "weibo"]
