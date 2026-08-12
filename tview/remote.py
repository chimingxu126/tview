"""遥控器输入模块（evdev）。

核心设计（修订版开发文档 1.1）：
- HOME 态：grab 独占设备，按键驱动 tview 界面
- APP 态：ungrab 让按键自然流向 Waydroid 窗口；本模块改为被动监听，
  仅用于检测"长按返回 3 秒回主页"
- 设备热插拔：读事件出错时自动重新扫描 /dev/input
- **多设备支持**：2.4G 遥控器接收器常拆成多个接口（键盘=导航键、
  Consumer Control=音量/媒体键），必须全部打开，否则音量键会丢失

按键映射：
- 确认=KEY_ENTER      返回=KEY_BACKSPACE   菜单=KEY_MENU   主页=KEY_HOME
- 方向=KEY_UP/DOWN/LEFT/RIGHT
- 音量=KEY_VOLUMEUP/KEY_VOLUMEDOWN
- 手柄：A/B/X/Y 对应确认/返回/菜单/主页（游戏手柄键位）
"""
from __future__ import annotations

import glob
import logging
import select
import threading
import time
from dataclasses import dataclass, field

import evdev
from evdev import InputDevice, ecodes

logger = logging.getLogger("tview.remote")

# 方向/功能键集合（含本遥控器的非标准码）
_DPAD = {ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT}
_CONFIRM = {ecodes.KEY_ENTER, ecodes.BTN_SOUTH}          # 确认：回车 / 手柄 A(×)
# 返回：退格(标准) / KEY_BACK(本遥控器 CC 接口) / 手柄 B(○)
_BACK = {ecodes.KEY_BACKSPACE, ecodes.KEY_BACK, ecodes.BTN_EAST}
# 菜单：KEY_MENU(标准) / KEY_COMPOSE(本遥控器) / 手柄 X(□)
_MENU = {ecodes.KEY_MENU, ecodes.KEY_COMPOSE, ecodes.BTN_WEST}
# 主页：KEY_HOME(标准) / KEY_HOMEPAGE(本遥控器) / 手柄 Y(△)
_HOME = {ecodes.KEY_HOME, ecodes.KEY_HOMEPAGE, ecodes.BTN_NORTH}
_VOL_UP = {ecodes.KEY_VOLUMEUP}
_VOL_DOWN = {ecodes.KEY_VOLUMEDOWN}
_POWER = {ecodes.KEY_POWER}

# 设备级映射覆盖（实测数据 2026-08-08）：设备名子串 -> {keycode: 动作}
# 优先级高于全局映射。此遥控器把“设置键”发成退格码(14)，必须按设备区分。
DEVICE_KEYMAPS = {
    "usb composite device": {
        14: "settings",      # 设置键（实测）
        127: "menu",         # 菜单键（实测）
        111: "ignore",       # 信号源键（实测，用不上）
        158: "back",         # 返回键（实测）
        172: "home",         # 主页键（实测）
        115: "volume_up",    # 音量+（实测）
        114: "volume_down",  # 音量-（实测）
        28: "enter",         # OK（实测）
        103: "up", 108: "down", 105: "left", 106: "right",  # 方向
    },
}


def _global_action(code: int) -> str | None:
    """全局默认映射：标准键码 -> 动作。"""
    if code in _POWER:
        return "power"
    if code in _VOL_UP:
        return "volume_up"
    if code in _VOL_DOWN:
        return "volume_down"
    if code in _HOME:
        return "home"
    if code in _DPAD:
        return {ecodes.KEY_UP: "up", ecodes.KEY_DOWN: "down",
                ecodes.KEY_LEFT: "left", ecodes.KEY_RIGHT: "right"}[code]
    if code in _CONFIRM:
        return "enter"
    if code in _BACK:
        return "back"
    if code in _MENU:
        return "menu"
    return None


def _action_for(code: int, dev: InputDevice | None = None) -> str | None:
    """解析按键动作：设备级映射优先，其次全局默认。"""
    if dev is not None:
        name = (dev.name or "").lower()
        for key, kmap in DEVICE_KEYMAPS.items():
            if key in name:
                return kmap.get(code) or _global_action(code)
    return _global_action(code)

# 排除的设备：虚拟输入（远程桌面）、音频、电源、视频总线等非遥控器设备
_EXCLUDE_NAME = (
    "AT Translated Set", "thinkpad", "logitech keyboard", "standard",
    "rustdesk", "uinput", "fake", "HDA", "Video Bus", "Power Button",
    "Sleep Button", "hdmi", "front mic", "rear mic", "headphone", "line out",
    "usb receiver mouse",
)
# 优先关键词：键盘接口 > 遥控器 > 2.4G > 接收器
_PREFER_KEYWORDS = ("keyboard", "remote", "air", "2.4", "receiver", "gamepad", "controller")


def _is_remote_capable(dev: InputDevice) -> bool:
    """判断设备是否像遥控器/手柄：带方向键 + 确认键，且不是主键盘/虚拟设备。"""
    name = (dev.name or "").lower()
    if any(k in name for k in _EXCLUDE_NAME):
        return False
    caps = dev.capabilities(verbose=False)
    keys = set()
    for key_type, key_list in caps.items():
        if key_type == ecodes.EV_KEY:
            keys.update(key_list)
    return bool(keys & _DPAD) and bool(keys & _CONFIRM)


def _device_score(dev: InputDevice) -> int:
    """设备优先级：名字含关键词的得分更高（键盘接口优先于 Consumer Control）。"""
    name = (dev.name or "").lower()
    score = 0
    for i, kw in enumerate(_PREFER_KEYWORDS):
        if kw in name:
            score += (len(_PREFER_KEYWORDS) - i) * 10
    return score


def scan_remotes(filter_name: str = "") -> list[InputDevice]:
    """扫描 /dev/input 下的遥控器/手柄设备（用 glob，不依赖 evdev.list_devices）。"""
    found: list[InputDevice] = []
    for path in glob.glob("/dev/input/event*"):
        try:
            dev = InputDevice(path)
            name = dev.name or ""
            if filter_name and filter_name.lower() not in name.lower():
                dev.close()
                continue
            if _is_remote_capable(dev):
                found.append(dev)
        except (PermissionError, OSError):
            continue  # 无权限/已移除的设备跳过
    found.sort(key=_device_score, reverse=True)
    return found


class Remote:
    """遥控器状态机：HOME(grab) / APP(被动监听)，支持多接口设备。"""

    # 回调：由 UI 注册（通过 Qt 信号桥接）
    on_key: "callable" = None          # on_key(action: str)  HOME 态按键动作
    on_longpress_back: "callable" = None  # 长按返回 3 秒 → 回主页
    on_device_lost: "callable" = None  # 设备掉线提示
    on_remote_state: "callable" = None # on_remote_state(ok: bool) 设备在位/缺失

    def __init__(self, mock: bool = False, device_filter: str = "", longpress_ms: int = 3000,
                 keyd_mode: bool = False):
        """keyd_mode=True 时：keyd 已接管设备（grab 冲突），本模块不读设备，输入走 Qt 事件路径。"""
        self.mock = mock
        self.device_filter = device_filter
        self.longpress_ms = longpress_ms
        self.keyd_mode = keyd_mode
        self._state = "HOME"           # HOME | APP
        self._devs: list[InputDevice] = []
        self._grab = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pressed_at: dict[int, float] = {}  # 键码 -> 按下时间（长按检测）

    # ---- 状态控制 ----
    def start(self) -> None:
        """启动读线程。keyd 模式下不读设备（避免与 keyd 的 grab 冲突）。"""
        if self.mock:
            logger.info("mock 模式：遥控器模块不读取真实设备")
            return
        if self.keyd_mode:
            logger.info("keyd 模式：输入由 keyd 接管，走 Qt 事件路径")
            return
        self._thread = threading.Thread(target=self._loop, name="remote-reader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        for dev in self._devs:
            try:
                dev.ungrab()
                dev.close()
            except OSError:
                pass
        self._devs = []

    def set_state(self, state: str) -> None:
        """HOME=独占抓取；APP=释放抓取只监听。"""
        if state not in ("HOME", "APP"):
            return
        if state == self._state:
            return
        self._state = state
        logger.info("遥控器状态 -> %s", state)
        self._apply_grab(state == "HOME")

    def _apply_grab(self, grab: bool) -> None:
        """对全部已开设备执行/释放 EVIOCGRAB 独占。"""
        self._grab = grab
        for dev in self._devs:
            try:
                if grab:
                    dev.grab()
                else:
                    dev.ungrab()
            except OSError as e:
                logger.warning("%s grab(%s) 失败: %s", dev.name, grab, e)
        logger.info("grab(%s) 已应用于 %d 个设备", grab, len(self._devs))

    # ---- 事件循环 ----
    def _loop(self) -> None:
        """后台读线程：select 多路复用监听全部设备，处理按键/热插拔/长按。"""
        while not self._stop.is_set():
            if not self._devs:
                self._devs = self._acquire_all()
                if not self._devs:
                    self._report_state(False)
                    time.sleep(2)  # 没设备就等一会再扫
                    continue
                self._apply_grab(self._state == "HOME")
                self._report_state(True)
            try:
                fd_map = {dev.fd: dev for dev in self._devs}
                ready, _, _ = select.select(list(fd_map), [], [], 1.0)
                for fd in ready:
                    dev = fd_map[fd]
                    for event in dev.read():
                        if event.type == ecodes.EV_KEY:
                            self._handle_key(event, dev)
            except OSError:
                logger.warning("遥控器设备断开，重新扫描")
                self._device_lost()
                self._close_all()
                time.sleep(1)

    def _acquire_all(self) -> list[InputDevice]:
        """扫描并打开全部候选遥控器接口（键盘+Consumer Control 等）。"""
        devs = scan_remotes(self.device_filter)
        if not devs:
            logger.info("遥控器设备扫描：未找到候选设备（检查 input 组权限/接收器是否插入）")
            return []
        for dev in devs:
            logger.info("遥控器设备已打开: %s (%s)", dev.name, dev.path)
        return devs

    def _close_all(self) -> None:
        for dev in self._devs:
            try:
                dev.close()
            except OSError:
                pass
        self._devs = []

    def _handle_key(self, event, dev: InputDevice | None = None) -> None:
        """按键事件分发（按设备解析动作，设备级映射优先）。"""
        code, value = event.code, event.value
        action = _action_for(code, dev)
        if value == 1:  # 按下
            self._pressed_at[code] = time.monotonic()
            self._dispatch(action, code)
        elif value == 0:  # 抬起
            start = self._pressed_at.pop(code, None)
            if action == "back" and start and (time.monotonic() - start) >= self.longpress_ms / 1000:
                # 长按返回：无论 HOME/APP 都回主页
                logger.info("长按返回 %.1fs，回主页", time.monotonic() - start)
                if self.on_longpress_back:
                    self.on_longpress_back()
        # value==2 重复按下：忽略

    def _dispatch(self, action: str | None, code: int) -> None:
        """按动作分发；HOME 态驱动 UI，APP 态只保留电源/音量/长按返回。"""
        if action is None or action == "ignore":
            return
        if self._state == "APP" and action not in ("power", "volume_up", "volume_down"):
            # APP 态：普通按键交给 Waydroid（不 grab 自然流转），只监听长按返回
            return
        self._action(action)

    def _action(self, action: str) -> None:
        """统一回调出口。"""
        if self.on_key:
            try:
                self.on_key(action)
            except Exception as e:
                logger.error("按键回调异常: %s", e)

    def _device_lost(self) -> None:
        if self.on_device_lost:
            try:
                self.on_device_lost()
            except Exception:
                pass
        self._report_state(False)

    def _report_state(self, ok: bool) -> None:
        """上报遥控器设备在位状态。"""
        if self.on_remote_state:
            try:
                self.on_remote_state(ok)
            except Exception:
                pass
