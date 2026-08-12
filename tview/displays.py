"""显示器检测与识别（BETA 0.3：显示器唤醒 TVIEW）。

接口无关：直接读 Linux DRM 层 /sys/class/drm——HDMI/DP/VGA/DVI/USB-C 等
所有接口的显示器都会注册为 connector 节点，统一处理。

状态语义：
- status: connected / disconnected（显示器插没插、或关电源后 EDID 消失）
- dpms:   On / Off（显示器电源状态；status 保持 connected 时靠它区分开关）

"显示器开启"判定：status=connected 且 dpms=On。
监听方式：udevadm monitor（drm 事件）+ 轮询兜底（dpms 变化）。
"""
from __future__ import annotations

import glob
import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DRM_GLOB = "/sys/class/drm/card*-*"  # 新内核：连接器在顶层（card1-HDMI-A-1 / card1-DP-1）


# ---------------- EDID 解析 ----------------

def _pnp_to_str(code: int) -> str:
    """EDID 厂商 PNP ID（3 个 5-bit 字母：'A'+bits）。"""
    chars = []
    for shift in (10, 5, 0):
        chars.append(chr(ord("A") + ((code >> shift) & 0x1F) - 1))
    return "".join(chars)


def parse_edid(data: bytes) -> dict:
    """解析 128 字节标准 EDID：厂商/产品代码/显示器名称。"""
    if not data or len(data) < 128 or data[0:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return {}
    try:
        vendor = _pnp_to_str((data[8] << 8) | data[9])
    except Exception:
        vendor = ""
    product = (data[10] << 8) | data[11]
    name = ""
    # descriptor blocks: 54-71 / 72-89 / 90-107 / 108-125，0xFC=显示器名
    for off in (54, 72, 90, 108):
        block = data[off:off + 18]
        if len(block) == 18 and block[0] == 0x00 and block[1] == 0x00 and block[3] == 0xFC:
            name = block[5:].split(b"\x0a")[0].decode("ascii", "ignore").strip()
            break
    return {"vendor": vendor, "product": product, "name": name}


# ---------------- 连接器扫描 ----------------

def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _read_edid(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except Exception:
        return b""


def list_connectors() -> list[dict]:
    """扫描全部 DRM 连接器。"""
    out = []
    for p in sorted(glob.glob(DRM_GLOB)):
        name = os.path.basename(p)
        status = _read(os.path.join(p, "status"))
        dpms = _read(os.path.join(p, "dpms"))
        edid = _read_edid(os.path.join(p, "edid"))
        info = parse_edid(edid)
        out.append({
            "connector": name,          # 如 HDMI-A-1 / DP-1
            "interface": name.split("-")[0],  # HDMI / DP / VGA / DVI / USB-C
            "status": status,           # connected / disconnected
            "dpms": dpms,               # On / Off
            "on": status == "connected" and dpms == "On",
            "vendor": info.get("vendor", ""),
            "product": info.get("product", 0),
            "name": info.get("name", ""),
        })
    return out


def label(c: dict) -> str:
    """人类可读标签：'HDMI-A-1 · PHILIPS 55PUF7061'。"""
    ident = c.get("name") or (f"{c.get('vendor','')}-{c.get('product',0)}" if c.get("vendor") else c["connector"])
    return f"{c['connector']} · {ident}"


# ---------------- 状态监听 ----------------

def snapshot() -> dict[str, dict]:
    """当前连接器状态快照：{connector: {on: bool, status, dpms}}。"""
    return {c["connector"]: {"on": c["on"], "status": c["status"], "dpms": c["dpms"]}
            for c in list_connectors()}


def wait_drm_event(timeout: float = 8.0) -> bool:
    """监听一次 udev drm 事件；超时返回 False。"""
    try:
        r = subprocess.run(
            ["udevadm", "monitor", "--subsystem-match=drm", "--property"],
            capture_output=True, text=True, timeout=timeout,
        )
        return True  # 有输出即代表事件（timeout 会抛异常）
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        logger.warning("udevadm monitor 失败: %s", e)
        return False


def display_on_events(interval: float = 2.0, poll_every: int = 15):
    """生成器：持续监测，返回新开启的显示器 connector 名列表。
    监听 udev drm 事件；每 poll_every 次轮询一次兜底（dpms 变化不一定触发事件）。"""
    prev = snapshot()
    polls = 0
    while True:
        if polls % poll_every == 0:
            cur = snapshot()
        else:
            cur = None
            wait_drm_event(interval)  # 阻塞到事件或超时
            cur = snapshot()
        polls += 1
        opened = []
        for conn, st in cur.items():
            old = prev.get(conn, {})
            if st["on"] and not old.get("on", False):
                opened.append(conn)
        if opened:
            yield opened
        prev = cur
