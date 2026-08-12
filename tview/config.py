"""配置管理：读取/写入 ~/.config/tview/config.yaml。"""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

import yaml

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "tview"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
LOG_DIR = CONFIG_DIR / "logs"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "tview"
LINUX_APPS_FILE = CONFIG_DIR / "linux_apps.json"
# Waydroid 导出图标目录（waydroid-launcher 同款约定）
WAYDROID_ICON_DIR = Path("~/.local/share/waydroid/data/icons").expanduser()

# 默认配置：与修订版开发文档一致（223.5.5.5 而非 8.8.8.8）
DEFAULTS = {
    "columns": 3,                 # 网格列数 2~6
    "background": "#1a1a2e",      # 深色背景
    "wallpaper": "",              # 自定义壁纸路径（空=纯色）
    "ping_target": "223.5.5.5",   # 网络探测目标（国内可达）
    "remote_device_filter": "",   # 遥控器设备名过滤（空=自动）
    "remote_longpress_back_ms": 3000,  # 长按返回回主页时长
    "wd_status_show": True,      # 显示 Waydroid 状态标签（默认显示）
    "watchdog_interval_s": 30,    # 看门狗间隔
    "watchdog_max_restart": 3,    # 连续失败重启上限
    "install_unknown": False,     # 保留位
    "energy_save": False,         # 节能模式（v0.1 实现，阶段1仅存配置）
    "autostart": True,            # 开机自动启动 TVIEW（设置里可开关，写 ~/.config/autostart/）
    "remote_keymap": {},          # 自定义遥控器映射 {Qt键值(int): 动作(str)}，空=用系统默认
    "language": "zh",            # 界面语言 zh/en（i18n.py，重启生效）
    "autologin": False,           # 开机免密直接进 TVIEW（GDM autologin，设置里可开关）
    "theme": "minimal",          # 主题：minimal/aurora/tech/space/bright/custom（theme.py）
    "custom_theme": {},           # 自定义主题配色覆盖（theme=自定义 时生效）
}


class Config:
    """配置读写，带线程锁。"""

    def __init__(self, path: Path = CONFIG_FILE, mock: bool = False):
        self.mock = mock
        self.path = path
        self._lock = threading.Lock()
        self.data = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        """从 YAML 加载，缺字段用默认值。"""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict):
                    self.data.update({k: v for k, v in loaded.items() if v is not None})
            except Exception as e:  # 配置损坏不致命
                self._log(f"配置文件解析失败: {e}，使用默认配置")
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """写回 YAML。"""
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.data, f, allow_unicode=True, sort_keys=False)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value

    @staticmethod
    def _log(msg: str) -> None:
        print(f"[config] {msg}")
