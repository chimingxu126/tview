#!/usr/bin/env python3
"""按键监听：打印指定 /dev/input 设备的按键事件（keycode + 名称）。用法: listen_keys.py <设备路径> <秒数>"""
import sys, time
from evdev import InputDevice, ecodes

path = sys.argv[1]
seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 60
dev = InputDevice(path)
print(f"监听 {dev.name} ({dev.path}) {seconds}s，请按键...", flush=True)
end = time.time() + seconds
try:
    for event in dev.read_loop():
        if time.time() > end:
            break
        if event.type == ecodes.EV_KEY and event.value == 1:  # 按下
            print(f"KEY: {ecodes.KEY.get(event.code, event.code)} (code={event.code})", flush=True)
except Exception as e:
    print(f"结束: {e}")
