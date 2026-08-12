"""Waydroid 命令封装：list / launch / install / status。

prod 模式真实执行命令；mock 模式仅打印日志并返回模拟数据。
所有耗时调用带超时保护。
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import WAYDROID_ICON_DIR

logger = logging.getLogger("tview.waydroid")

# Waydroid 导出的应用缓存（GNOME 应用列表同源）
DESKTOP_DIR = Path("~/.local/share/applications").expanduser()

# 模拟数据：mock 模式下展示的假应用
MOCK_APPS = [
    {"name": "当贝市场", "packageName": "com.dangbeimarket"},
    {"name": "电视家", "packageName": "com.ys.cctv"},
    {"name": "哔哩哔哩", "packageName": "tv.danmaku.bili"},
    {"name": "Kodi", "packageName": "org.xbmc.kodi"},
    {"name": "F-Droid", "packageName": "org.fdroid.fdroid"},
]


@dataclass
class AndroidApp:
    """安卓应用条目。"""
    name: str
    package: str
    icon: str = ""  # 图标路径，可为空


class Waydroid:
    """waydroid 命令封装。"""

    def __init__(self, mock: bool = False, timeout: int = 60):
        self.mock = mock
        self.timeout = timeout
        self._bin = shutil.which("waydroid")

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行命令；mock 模式只打日志。
        注意：waydroid 部分输出走 stderr（logging），统一合并处理。
        """
        cmd = ["waydroid", *args] if self._bin else ["echo", "waydroid-not-found", *args]
        logger.info("CMD: %s", " ".join(cmd))
        if self.mock:
            # mock 模式：不执行，返回空结果
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
        except subprocess.TimeoutExpired:
            logger.error("命令超时: %s", " ".join(cmd))
            return subprocess.CompletedProcess(cmd, 124, stdout="", stderr="timeout")

    @staticmethod
    def _text(r: subprocess.CompletedProcess) -> str:
        """合并 stdout+stderr（waydroid 经常把内容打到 stderr）。"""
        return (r.stdout or "") + (r.stderr or "")

    def status(self) -> str:
        """返回 waydroid status 输出（Session/Container 状态）。"""
        if self.mock:
            return "Session:\tRUNNING (mock)\nContainer:\tRUNNING (mock)"
        return self._text(self._run(["status"]))

    def session_running(self) -> bool:
        """会话是否在运行（看门狗用；合并输出解析，避免 stderr 误判）。"""
        out = self.status()
        return "Session:" in out and "RUNNING" in out

    def status_state(self) -> str:
        """状态机：running（已启动）| frozen（休眠冻结）| starting（启动中）| stopped（未启动）。"""
        if self.mock:
            return "running"
        out = self.status()
        if "Session:" in out:
            if "RUNNING" in out:
                # 容器被 Android 休眠机制冻结（非故障，启动应用时自动解冻）
                if "Container:" in out and "FROZEN" in out:
                    return "frozen"
                return "running"
            if "STOPPED" in out:
                return "stopped"
        return "starting"  # 中间态/未知

    def session_start(self) -> bool:
        """启动 Waydroid 会话（需 Wayland 显示环境；盒子模式可用）。"""
        r = self._run(["session", "start"])
        return r.returncode == 0

    def session_stop(self) -> bool:
        """停止 Waydroid 会话。"""
        r = self._run(["session", "stop"])
        return r.returncode == 0

    def app_list(self) -> list[AndroidApp] | None:
        """获取安卓应用列表。
        优先读 Waydroid 导出的 .desktop 缓存（离线可用、毫秒级）；
        无缓存时回退 `waydroid app list`（容器未就绪返回 None）。
        """
        if self.mock:
            return [AndroidApp(a["name"], a["packageName"]) for a in MOCK_APPS]
        cached = self._apps_from_desktop()
        if cached is not None:
            return cached
        r = self._run(["app", "list"])
        out = self._text(r)
        if not out.strip():
            logger.warning("waydroid app list 输出为空（容器/会话未就绪）")
            return None
        apps: list[AndroidApp] = []
        name, pkg = "", ""
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("packageName:"):
                pkg = line.split(":", 1)[1].strip()
                if name and pkg:
                    apps.append(AndroidApp(name, pkg, self._find_icon(pkg)))
                name, pkg = "", ""
        return apps

    def _apps_from_desktop(self) -> list[AndroidApp] | None:
        """读 Waydroid 导出的 .desktop 缓存（Name/Icon/launch 包名）。
        有缓存返回应用列表；无任何缓存返回 None（调用方回退 app list）。
        """
        if not DESKTOP_DIR.exists():
            return None
        apps: list[AndroidApp] = []
        for f in DESKTOP_DIR.glob("waydroid.*.desktop"):
            try:
                name = pkg = icon = ""
                for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("[Desktop Action"):
                        break  # 只解析主条目
                    if line.startswith("Name="):
                        name = line.split("=", 1)[1].strip()
                    elif line.startswith("Icon="):
                        icon = line.split("=", 1)[1].strip()
                    elif line.startswith("Exec="):
                        toks = line[5:].split()
                        if len(toks) >= 4 and toks[2] == "launch":
                            pkg = toks[3]
                if name and pkg:
                    apps.append(AndroidApp(name, pkg, icon if Path(icon).exists() else ""))
            except Exception:
                continue
        if not apps:
            return None
        logger.info("从 .desktop 缓存读取 %d 个安卓应用", len(apps))
        return apps

    def _find_icon(self, package: str) -> str:
        """在 Waydroid 图标导出目录找应用图标（png）。"""
        for suffix in (".png", ".jpg", ".webp"):
            p = WAYDROID_ICON_DIR / f"{package}{suffix}"
            if p.exists():
                return str(p)
        # 兜底：目录内按包名前缀模糊匹配
        if WAYDROID_ICON_DIR.exists():
            for f in WAYDROID_ICON_DIR.iterdir():
                if f.stem == package or f.stem.startswith(package + "_"):
                    return str(f)
        return ""

    def app_launch(self, package: str) -> bool:
        """启动安卓应用。"""
        r = self._run(["app", "launch", package])
        return r.returncode == 0

    def app_install(self, apk_path: str | Path) -> bool:
        """安装 APK（宿主侧命令，绕开安卓未知来源限制）。"""
        r = self._run(["app", "install", str(apk_path)])
        return r.returncode == 0

    def app_uninstall(self, package: str) -> bool:
        """卸载应用。"""
        r = self._run(["app", "remove", package])
        return r.returncode == 0
