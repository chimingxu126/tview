#!/usr/bin/env python3
"""启视·TVIEW 按键测试小应用（可独立运行，也是"学习模式"的数据采集底座）。

功能：
- 实时显示按下的键：键名 + keycode + 来自哪个设备/接口
- 标准键位面板（方向/OK/返回/主页/菜单/音量/设置/数字）高亮反馈
- 未知按键自动落入"自定义"区显示
- 可导出本次按键数据为 JSON（后续映射库的数据来源）

用法：
    python3 key_tester.py            # 打开测试界面
    python3 key_tester.py --no-gui   # 纯命令行监听（无 PyQt 环境可用）
"""
from __future__ import annotations

import glob
import json
import select
import sys
import threading
import time

import evdev
from evdev import InputDevice, ecodes

# 排除非遥控器设备
EXCLUDE = ("rustdesk", "uinput", "fake", "HDA", "power button", "sleep",
           "video bus", "at translated", "thinkpad", "front mic", "rear mic",
           "headphone", "line out", "hdmi", "logitech keyboard", "standard")

# 标准键位表：keycode -> 显示名
KEY_NAMES = {
    ecodes.KEY_UP: "⬆ 上", ecodes.KEY_DOWN: "⬇ 下", ecodes.KEY_LEFT: "⬅ 左",
    ecodes.KEY_RIGHT: "➡ 右", ecodes.KEY_ENTER: "OK 确认", ecodes.KEY_BACK: "返回",
    ecodes.KEY_BACKSPACE: "退格", ecodes.KEY_HOMEPAGE: "主页", ecodes.KEY_HOME: "主页(标准)",
    ecodes.KEY_MENU: "菜单", ecodes.KEY_COMPOSE: "菜单(Compose)", ecodes.KEY_SETUP: "设置",
    ecodes.KEY_VOLUMEUP: "音量+", ecodes.KEY_VOLUMEDOWN: "音量-", ecodes.KEY_MUTE: "静音",
    ecodes.KEY_POWER: "电源", ecodes.KEY_DELETE: "删除/信号源", ecodes.KEY_TV: "TV",
    ecodes.KEY_1: "1", ecodes.KEY_2: "2", ecodes.KEY_3: "3", ecodes.KEY_4: "4",
    ecodes.KEY_5: "5", ecodes.KEY_6: "6", ecodes.KEY_7: "7", ecodes.KEY_8: "8",
    ecodes.KEY_9: "9", ecodes.KEY_0: "0",
}
# 设备级键名（实测 2026-08-08，与 tview 设备映射保持一致）：
# 设备名子串 -> {keycode: 功能名}
DEVICE_NAMES = {
    "usb composite device": {
        14: "设置键",          # KEY_BACKSPACE（实测）
        127: "菜单键",         # KEY_COMPOSE（实测）
        111: "信号源键",       # KEY_DELETE（实测，用不上）
        158: "返回",           # KEY_BACK（实测）
        172: "主页",           # KEY_HOMEPAGE（实测）
        115: "音量+",          # KEY_VOLUMEUP（实测）
        114: "音量-",          # KEY_VOLUMEDOWN（实测）
        28: "OK",              # KEY_ENTER（实测）
        103: "上", 108: "下", 105: "左", 106: "右",
    },
}

# 面板显示顺序（学习模式/测试界面用）
PANEL = ["上", "下", "左", "右", "OK", "返回", "主页", "菜单键",
         "音量+", "音量-", "静音", "设置键", "电源", "1", "2", "3", "4", "5",
         "6", "7", "8", "9", "0"]


def open_devices() -> list[InputDevice]:
    """打开全部未被排除的输入设备。"""
    devs = []
    for path in sorted(glob.glob("/dev/input/event*"), key=lambda p: int(p.split("event")[1])):
        try:
            dev = InputDevice(path)
            name = (dev.name or "").lower()
            if any(k in name for k in EXCLUDE):
                dev.close()
                continue
            devs.append(dev)
        except (PermissionError, OSError):
            continue
    return devs


def listen(on_key) -> None:
    """后台监听线程：on_key(dev_name, code, value)"""
    def loop():
        while True:
            devs = open_devices()
            if not devs:
                time.sleep(2)
                continue
            try:
                while True:
                    fd_map = {d.fd: d for d in devs}
                    ready, _, _ = select.select(list(fd_map), [], [], 1.0)
                    for fd in ready:
                        dev = fd_map[fd]
                        for event in dev.read():
                            if event.type == ecodes.EV_KEY and event.value == 1:
                                on_key(dev.name or "", event.code)
            except OSError:
                time.sleep(1)
    threading.Thread(target=loop, daemon=True).start()


def key_label(code: int, dev_name: str = "") -> str:
    """键码显示名：设备级实测名优先，其次标准表，未知显示 自定义(code)。"""
    dname = (dev_name or "").lower()
    for key, kmap in DEVICE_NAMES.items():
        if key in dname and code in kmap:
            return kmap[code]
    return KEY_NAMES.get(code, f"自定义({code})")


# ---------------- 无 GUI 模式 ----------------
def run_cli() -> int:
    print("按键监听中（Ctrl+C 退出）。按你的遥控器各键试试：")
    seen: dict[int, str] = {}

    def on_key(dev_name: str, code: int):
        label = key_label(code, dev_name)
        print(f"  {label:<12} code={code:<4} 设备: {dev_name}")
        seen[code] = label

    listen(on_key)
    try:
        time.sleep(10**9)
    except KeyboardInterrupt:
        pass
    print("\n=== 本次按键汇总 ===")
    for code, label in sorted(seen.items()):
        print(f"  {code}: {label}")
    return 0


# ---------------- GUI 模式 ----------------
def run_gui() -> int:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel,
                                 QPushButton, QVBoxLayout, QWidget)

    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("启视·TVIEW 按键测试")
    win.setStyleSheet("QWidget{background:#1a1a2e;color:#eee;} QLabel{font-size:16px;}")
    root = QVBoxLayout(win)

    # 顶部：最后按键信息
    info = QLabel("等待按键…（请按下遥控器上的任意键）")
    info.setStyleSheet("font-size:20px;color:#7ee787;background:#16213e;padding:10px;border-radius:6px;")
    root.addWidget(info)

    # 标准键位面板
    panel = QGridLayout()
    cells: dict[str, QPushButton] = {}
    for i, name in enumerate(PANEL):
        btn = QPushButton(name)
        btn.setEnabled(False)
        btn.setStyleSheet(
            "QPushButton{font-size:14px;min-height:40px;background:#16213e;border:1px solid #3a4a6b;border-radius:6px;}"
            "QPushButton:disabled{color:#888;}"
        )
        cells[name] = btn
        panel.addWidget(btn, i // 5, i % 5)
    root.addLayout(panel)

    # 自定义区
    custom_label = QLabel("自定义按键（未在标准表中的）：")
    root.addWidget(custom_label)
    custom_box = QVBoxLayout()
    root.addLayout(custom_box)

    # 导出按钮
    export_btn = QPushButton("📤 导出按键数据 (JSON)")
    export_btn.setStyleSheet("QPushButton{font-size:16px;padding:10px;background:#16213e;border:1px solid #3a4a6b;}")
    root.addWidget(export_btn)

    pressed: dict[int, str] = {}

    def on_key(dev_name: str, code: int):
        label = key_label(code, dev_name)
        info.setText(f"✅ {label}  (keycode={code})  设备: {dev_name}")
        pressed[code] = {"label": label, "device": dev_name}
        if label in cells:
            btn = cells[label]
            btn.setStyleSheet(
                "QPushButton{font-size:14px;min-height:40px;background:#e94560;border:2px solid #fff;border-radius:6px;}"
            )
            # 2 秒后恢复
            threading.Timer(2.0, lambda: btn.setStyleSheet(
                "QPushButton{font-size:14px;min-height:40px;background:#16213e;border:1px solid #3a4a6b;border-radius:6px;}"
                "QPushButton:disabled{color:#888;}"
            )).start()
        else:
            # 未知键加入自定义区
            lbl = QLabel(f"  {label}  code={code}  设备: {dev_name}")
            custom_box.addWidget(lbl)
            info.setText(f"⚠️ 未知键 {label} (code={code}) — 可用于自定义映射")

    def export_data():
        path = f"keymap-{time.strftime('%Y%m%d-%H%M%S')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pressed, f, ensure_ascii=False, indent=2)
        info.setText(f"✅ 已导出 {len(pressed)} 个键位 → {path}")

    export_btn.clicked.connect(export_data)
    listen(on_key)
    win.resize(560, 620)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    if "--no-gui" in sys.argv:
        sys.exit(run_cli())
    sys.exit(run_gui())
