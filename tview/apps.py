"""统一应用模型：安卓应用（Waydroid） + Linux 原生应用（linux_apps.json）。"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from .config import LINUX_APPS_FILE
from .waydroid import AndroidApp, Waydroid

logger = logging.getLogger("tview.apps")


@dataclass
class App:
    """统一应用卡片。"""
    name: str
    kind: str            # "android" | "linux"
    launch: str          # 安卓包名 或 Linux 命令
    icon: str = ""       # 图标路径
    extra: dict = field(default_factory=dict)


class AppManager:
    """合并安卓 + Linux 应用，统一成 App 卡片列表。"""

    def __init__(self, waydroid: Waydroid):
        self.waydroid = waydroid
        self._apps: list[App] = []
        self.waydroid_ok = False  # Waydroid 是否可读（离线时 Linux 应用照常显示）

    def refresh(self) -> list[App]:
        """重新扫描全部应用。Linux 应用与 Waydroid 解耦：Waydroid 挂了也照常加载。"""
        self._apps = []
        self.waydroid_ok = False
        try:
            android = self.waydroid.app_list()
            if android is None:
                logger.warning("Waydroid 不可用，仅加载 Linux 应用")
            else:
                self.waydroid_ok = True
                for a in android:
                    self._apps.append(App(name=a.name, kind="android", launch=a.package, icon=a.icon))
        except Exception as e:
            logger.error("读取安卓应用失败: %s", e)
        self._apps.extend(self._load_linux_apps())
        self._apps.sort(key=lambda x: x.name)
        return self._apps

    def apps(self) -> list[App]:
        return self._apps

    def _load_linux_apps(self) -> list[App]:
        """读取用户自定义 Linux 应用（名称/命令/图标）。"""
        out: list[App] = []
        if not LINUX_APPS_FILE.exists():
            return out
        try:
            with open(LINUX_APPS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                if item.get("name") and item.get("cmd"):
                    out.append(App(
                        name=item["name"], kind="linux",
                        launch=item["cmd"], icon=item.get("icon", ""),
                    ))
        except Exception as e:
            logger.error("读取 Linux 应用失败: %s", e)
        return out

    def add_linux_app(self, name: str, cmd: str, icon: str = "") -> None:
        """添加自定义 Linux 应用并持久化。"""
        apps = self._load_linux_apps()
        apps.append({"name": name, "cmd": cmd, "icon": icon})
        LINUX_APPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LINUX_APPS_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False, indent=2)
        self.refresh()
