"""显示器唤醒 TVIEW 后台监听（BETA 0.3）。

用法: tview --watch（桌面模式自启；盒子模式不需要——TVIEW 常驻）
检测到目标显示器开启 → 启动 TVIEW 全屏。

安全：不绕过任何认证（GNOME 锁屏时启动的 TVIEW 在解锁后可见，等同手动打开）；
L1 退出锁屏 / L2 盒子模式安全模型均不受影响。
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from .displays import display_on_events

logger = logging.getLogger(__name__)


def _tview_cmd() -> list[str]:
    """定位 tview 启动命令（PyInstaller 二进制 / 源码模式兼容）。"""
    exe = Path("/proc/self/exe").resolve()
    if "python" in exe.name.lower():
        return [sys.executable, str(Path(sys.argv[0]).resolve()), "--prod"]
    return [str(exe), "--prod"]


def _launch_tview() -> None:
    # 已在运行则跳过（盒子模式常驻 / 用户已手动打开时不重复启动）
    try:
        r = subprocess.run(["pgrep", "-f", "tview --prod"], capture_output=True)
        if r.returncode == 0:
            logger.info("TVIEW 已在运行，跳过重复启动")
            return
    except Exception:
        pass
    try:
        subprocess.Popen(_tview_cmd())
        logger.info("已启动 TVIEW")
    except Exception as e:
        logger.error("启动 TVIEW 失败: %s", e)


def run_watch(config) -> int:
    """--watch 主循环：监听显示器开启事件，命中目标则启动 TVIEW。"""
    dw = config.get("display_wake") or {}
    if not dw.get("enabled", True):
        logger.info("显示器唤醒 TVIEW 已关闭（设置里开启）")
        return 0
    mode = dw.get("mode", "any")  # any / specific
    targets = set(dw.get("targets") or [])
    if mode == "specific" and not targets:
        logger.info("特定显示器模式但未选择显示器，等待设置…")
    logger.info("显示器唤醒监听启动 mode=%s targets=%s", mode, sorted(targets))

    for opened in display_on_events():
        if mode == "any":
            hit = opened
        else:
            hit = [c for c in opened if c in targets]
        if hit:
            logger.info("显示器开启: %s → 唤醒 TVIEW", hit)
            _launch_tview()
    return 0
