"""全局配置 - 基于pydantic-settings，自动读取.env"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # 基础
    app_name: str = "内容创作系统"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me-in-production"

    # 数据库
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'app.db'}"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # 通知
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    notify_email: str = ""

    # 媒体下载器
    media_downloader_url: str = "https://twitter-media-downloader.onrender.com"

    # 爬虫
    crawler_headless: bool = True
    crawler_proxy: str = ""
    crawler_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    # 平台Cookie
    xhs_cookie: str = ""
    douyin_cookie: str = ""
    bilibili_cookie: str = ""
    weibo_cookie: str = ""

    # 路径
    data_dir: Path = BASE_DIR / "data"
    raw_dir: Path = BASE_DIR / "data" / "raw"
    processed_dir: Path = BASE_DIR / "data" / "processed"
    reports_dir: Path = BASE_DIR / "data" / "reports"
    scripts_output_dir: Path = BASE_DIR / "data" / "scripts_output"

    model_config = {"env_file": str(BASE_DIR / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
