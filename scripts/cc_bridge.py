#!/usr/bin/env python3
"""CC 接口桥接守护进程（uinput 重注入）。

问题：2.4G 遥控器的"返回/主页/音量"键走 Consumer Control 接口，
而 Waydroid 的合成器（weston/Cage，基于 libinput）不把纯媒体键设备
归类为键盘，导致这些按键到不了安卓。

方案：本进程读取全部 CC 类遥控器设备，把按键事件通过 uinput 以
"标准键盘"身份重注入（设备名 tview_cc_bridge）。合成器看到的是一个
正常键盘 → 事件转发给 Waydroid → 安卓 Generic.kl 正常映射
（158→BACK / 172→HOME / 115/114→VOLUME）。

用法：
    python3 cc_bridge.py              # 前台运行
    python3 cc_bridge.py --daemon     # 后台运行（nohup）
依赖：evdev（需要 input 组权限或 root）
"""
from __future__ import annotations

import glob
import select
import sys
import time

import evdev
from evdev import InputDevice, UInput, ecodes

# 桥接设备名：合成器看到的"键盘"名，同时用于安卓 keylayout 匹配
BRIDGE_NAME = "tview_cc_bridge"
# 只桥接这些键（不重复注入方向/OK 等键盘接口已有的键）
BRIDGE_KEYS = {
    ecodes.KEY_BACK: "back",          # 158 返回
    ecodes.KEY_HOMEPAGE: "home",      # 172 主页
    ecodes.KEY_VOLUMEUP: "volup",     # 115 音量+
    ecodes.KEY_VOLUMEDOWN: "voldown", # 114 音量-
    ecodes.KEY_MUTE: "mute",          # 113 静音（若有）
}

EXCLUDE = ("rustdesk", "uinput", "fake", "HDA", "power button", "sleep", "video bus")


def find_cc_devices() -> list[InputDevice]:
    """找带音量键的 CC 类设备。"""
    found = []
    for path in sorted(glob.glob("/dev/input/event*"), key=lambda p: int(p.split("event")[1])):
        try:
            dev = InputDevice(path)
            name = (dev.name or "").lower()
            if any(k in name for k in EXCLUDE):
                dev.close()
                continue
            caps = dev.capabilities(verbose=False)
            keys = set()
            for kt, kl in caps.items():
                if kt == ecodes.EV_KEY:
                    keys.update(kl)
            if keys & {ecodes.KEY_VOLUMEUP, ecodes.KEY_VOLUMEDOWN}:
                found.append(dev)
        except (PermissionError, OSError):
            continue
    return found


def make_uinput() -> UInput:
    """创建 uinput 键盘设备（只注册按键能力）。"""
    caps = {ecodes.EV_KEY: list(BRIDGE_KEYS.keys())}
    return UInput(caps, name=BRIDGE_NAME, version=0x1)


def main() -> int:
    ui = make_uinput()
    print(f"✅ uinput 设备已创建: {BRIDGE_NAME}")
    devs = find_cc_devices()
    if not devs:
        print("❌ 未找到 CC 接口遥控器设备")
        ui.close()
        return 1
    for d in devs:
        print(f"   监听: {d.name} ({d.path})")
    print("桥接运行中，Ctrl+C 退出。")

    last_key = None
    while True:
        try:
            fd_map = {d.fd: d for d in devs}
            ready, _, _ = select.select(list(fd_map), [], [], 1.0)
            for fd in ready:
                dev = fd_map[fd]
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    code = event.code
                    if code not in BRIDGE_KEYS:
                        continue
                    # 重注入：按下/抬起
                    ui.write(ecodes.EV_KEY, code, event.value)
                    ui.sync()
                    if event.value == 1:
                        print(f"   桥接 {BRIDGE_KEYS[code]} (code={code})")
        except OSError:
            print("设备断开，重新扫描…")
            for d in devs:
                try:
                    d.close()
                except OSError:
                    pass
            devs = find_cc_devices()
            time.sleep(2)
        except KeyboardInterrupt:
            break
    ui.close()
    return 0


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        import subprocess
        subprocess.Popen([sys.executable, __file__],
                         stdout=open("/tmp/cc_bridge.log", "a"),
                         stderr=subprocess.STDOUT, start_new_session=True)
        print("已后台启动，日志: /tmp/cc_bridge.log")
        sys.exit(0)
    sys.exit(main())
