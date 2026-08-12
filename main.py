#!/usr/bin/env python3
"""启视·TVIEW Launcher 主入口。

用法:
    python3 main.py --mock           # 模拟模式（开发调试，不执行真实命令）
    python3 main.py --prod           # 生产模式（真实调用 waydroid/systemctl 等）
    python3 main.py --mock --render-out /tmp/tview.png   # 无显示环境渲染截图（开发验证）

阶段1范围：启动器网格 + 遥控器 grab/ungrab + Waydroid 应用管理 + 简版设置/市场。
"""
from __future__ import annotations

import argparse
import sys


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="启视·TVIEW Launcher")
    p.add_argument("--prod", action="store_true", help="生产模式：真实调用系统命令")
    p.add_argument("--mock", action="store_true", help="模拟模式：命令仅打印日志")
    p.add_argument("--render-out", default="", help="渲染一帧截图到该路径后退出（开发验证用）")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    mock = args.mock or not args.prod  # 默认 mock，避免误操作真实系统

    from tview.config import Config
    from tview.logging_setup import install_crash_hook, setup_logging
    from tview.i18n import set_language
    logger = setup_logging()
    install_crash_hook(logger)
    logger.info("TVIEW 启动 mode=%s render_out=%s", "mock" if mock else "prod", args.render_out or "-")

    config = Config(mock=mock)
    set_language(config.get("language", "zh"))

    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("启视·TVIEW")
    # 全局 QPalette：未被子控件 QSS 覆盖的文字一律用主题文字色（黑字问题根治）
    from PyQt5.QtGui import QColor, QPalette
    from tview.theme import build_qss, resolve_theme
    _theme = resolve_theme(config)
    pal = app.palette()
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                 QPalette.HighlightedText, QPalette.ToolTipText):
        pal.setColor(role, QColor(_theme["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(_theme["text_dim"]))
    app.setPalette(pal)
    # 全局样式表：按主题生成，所有弹窗/QMessageBox 都生效
    app.setStyleSheet(build_qss(_theme))

    from tview.remote import Remote
    from tview.waydroid import Waydroid
    from tview.apps import AppManager
    from tview.ui.main_window import MainWindow

    # keyd 检测：keyd 运行时输入由它接管（避免 grab 冲突），否则走 evdev
    keyd_on = False
    if not mock:
        try:
            import subprocess as _sp
            keyd_on = _sp.run(["pgrep", "-x", "keyd.rvaiya"], capture_output=True).returncode == 0
        except Exception:
            keyd_on = False
    config.set("input_keyd", keyd_on)
    logger.info("输入模式: %s", "keyd" if keyd_on else "evdev")

    waydroid = Waydroid(mock=mock)
    app_mgr = AppManager(waydroid)
    remote = Remote(
        mock=mock,
        device_filter=config.get("remote_device_filter", ""),
        longpress_ms=int(config.get("remote_longpress_back_ms", 3000)),
        keyd_mode=keyd_on,
    )
    win = MainWindow(config, waydroid, app_mgr, remote)
    win.refresh_apps()
    remote.start()

    if args.render_out:
        # 开发验证：离屏渲染一帧存图
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (win.grab().save(args.render_out), app.quit()))
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
