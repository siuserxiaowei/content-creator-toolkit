"""内容创作系统 - 主入口"""

import asyncio
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from core.logger import get_logger
from storage.database import init_db

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info(f"🚀 {settings.app_name} 启动中...")
    await init_db()
    logger.info("数据库初始化完成")

    # 启动调度器
    from core.scheduler.engine import start_scheduler
    await start_scheduler()
    logger.info("调度器已启动")

    yield

    logger.info(f"{settings.app_name} 已关闭")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API路由
from api.router import api_router
app.include_router(api_router, prefix="/api/v1")


# Web前端
WEB_DIR = Path(__file__).parent / "web"


@app.get("/")
async def root():
    """返回管理后台页面"""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
async def health():
    return {"name": settings.app_name, "version": "0.1.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)
