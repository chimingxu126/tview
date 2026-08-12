#!/usr/bin/env python3
"""发布截图生成：offscreen 渲染主界面 + 设置弹窗，存到 docs/screenshots/。"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QPalette

from tview.config import Config
from tview.logging_setup import setup_logging
from tview.i18n import set_language
from tview.theme import build_qss, resolve_theme
from tview.remote import Remote
from tview.waydroid import Waydroid
from tview.apps import AppManager
from tview.ui.main_window import MainWindow

setup_logging()
out_dir = Path(_REPO) / "docs" / "screenshots"
out_dir.mkdir(parents=True, exist_ok=True)

# 隔离配置：读真实应用缓存但用临时配置（theme 手动指定）
_cfg_path = Path("/tmp/tview-shot-config.yaml")
if _cfg_path.exists():
    _cfg_path.unlink()
config = Config(path=_cfg_path, mock=True)
config.set("columns", 4)
set_language("zh")

app = QApplication(sys.argv)
app.setApplicationName("启视·TVIEW")


def apply_theme():
    theme = resolve_theme(config)
    pal = app.palette()
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                 QPalette.HighlightedText, QPalette.ToolTipText):
        pal.setColor(role, QColor(theme["text"]))
    app.setPalette(pal)
    app.setStyleSheet(build_qss(theme))
    return theme


def make_window(theme_key: str):
    config.set("theme", theme_key)
    apply_theme()
    waydroid = Waydroid(mock=False)   # 读真实 waydroid .desktop 缓存（17 个应用）
    mgr = AppManager(waydroid)
    remote = Remote(mock=True)
    win = MainWindow(config, waydroid, mgr, remote)
    win.refresh_apps()
    return win


def shot(win, path: str, wait_ms: int = 2600):
    done = {"ok": False}

    def _do():
        win.grab().save(path)
        done["ok"] = True
        app.quit()
    QTimer.singleShot(wait_ms, _do)
    app.exec_()
    print(f"已保存: {path}")


# 1) 极光主题主界面（真实安卓应用）
win = make_window("aurora")
win.resize(1280, 720)
shot(win, str(out_dir / "main-aurora.png"))

# 2) 科技蓝主题主界面
win = make_window("tech")
win.resize(1280, 720)
shot(win, str(out_dir / "main-tech.png"))
print("截图生成完毕")
