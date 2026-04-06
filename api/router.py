"""API路由汇总"""

from fastapi import APIRouter

api_router = APIRouter()


# 延迟导入各子路由，避免循环依赖
@api_router.on_event("startup")
async def _():
    pass


from api.kol import router as kol_router
from api.content import router as content_router
from api.monitor import router as monitor_router
from api.analysis import router as analysis_router
from api.script import router as script_router

api_router.include_router(kol_router, prefix="/kols", tags=["KOL管理"])
api_router.include_router(content_router, prefix="/contents", tags=["内容管理"])
api_router.include_router(monitor_router, prefix="/monitor", tags=["监控管理"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["选题分析"])
api_router.include_router(script_router, prefix="/scripts", tags=["脚本生成"])
