"""日志初始化：tview.log 滚动（最大 10MB）+ crash.log 异常转储。"""
from __future__ import annotations

import logging
import logging.handlers
import sys
import traceback
from datetime import datetime

from .config import LOG_DIR


def setup_logging() -> logging.Logger:
    """初始化滚动日志，返回应用 logger。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tview")
    if logger.handlers:  # 避免重复初始化
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "tview.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    return logger


def install_crash_hook(logger: logging.Logger) -> None:
    """全局异常钩子：未捕获异常写入 crash.log。"""

    def hook(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("未捕获异常:\n%s", msg)
        try:
            with open(LOG_DIR / "crash.log", "a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.now().isoformat()} =====\n{msg}")
        except Exception:
            pass

    sys.excepthook = hook
