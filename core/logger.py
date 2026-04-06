"""统一日志系统 - 基于loguru，同时写文件和控制台"""

import sys
from pathlib import Path
from loguru import logger

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 移除默认handler
logger.remove()

# 控制台输出 - 彩色简洁
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# 文件输出 - 详细，按天轮转
logger.add(
    LOG_DIR / "app_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    compression="gz",
    encoding="utf-8",
)

# 错误单独一份日志
logger.add(
    LOG_DIR / "error_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function}:{line} - {message}\n{exception}",
    level="ERROR",
    rotation="00:00",
    retention="60 days",
    compression="gz",
    encoding="utf-8",
)


def get_logger(name: str = ""):
    """获取带模块标记的logger"""
    if name:
        return logger.bind(module=name)
    return logger
