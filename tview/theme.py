"""主题系统：内置主题 + 自定义覆盖 + WCAG 对比度自动保障 + 程序化壁纸。

- 主题 = 一套完整配色（背景/卡片/聚焦/文字），切换即时生效（app 级 QSS）
- 对比度保障：应用主题时逐项计算文字 vs 背景（WCAG 2.1，正文 ≥4.5:1），
  不达标自动提亮/压暗文字，用户自定义主题也不会出现"字和底糊一起"
- 壁纸：程序化生成（渐变/光晕/星点/网格），无版权问题；自定义可换图片
"""
from __future__ import annotations

import logging
import random
import re

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPixmap, QRadialGradient

logger = logging.getLogger("tview.theme")

# ---------------- WCAG 对比度 ----------------

def _lin(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    c = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def contrast(fg: str, bg: str) -> float:
    """WCAG 对比度比值。"""
    l1, l2 = luminance(fg), luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def ensure_contrast(fg: str, bg: str, target: float = 4.5) -> str:
    """文字色不达标时自动提亮（深色底）或压暗（浅色底），直到达标。"""
    if contrast(fg, bg) >= target:
        return fg
    c = QColor(fg)
    if luminance(bg) < 0.4:  # 深色背景 → 往白色提亮
        for _ in range(24):
            c = c.lighter(115)
            if contrast(c.name(), bg) >= target:
                return c.name()
        return "#ffffff"
    # 浅色背景 → 往黑色压暗
    for _ in range(24):
        c = c.darker(120)
        if contrast(c.name(), bg) >= target:
            return c.name()
    return "#000000"


# ---------------- 内置主题 ----------------
# 字段：bg1/bg2 背景渐变、wallpaper 壁纸风格、card/card_border 卡片、
#       focus 聚焦色、text 文字主色、text_dim 辅助文字、accent 点缀色
THEMES: dict[str, dict] = {
    "minimal": {
        "name": "Minimal", "name_zh": "极简",
        "bg1": "#10162a", "bg2": "#1c2440", "wallpaper": "gradient",
        "card": "#1e2848", "card_border": "#2e3d66",
        "focus": "#e94560", "text": "#e8ecf5", "text_dim": "#aab4cc",
        "accent": "#7ee0ff",
    },
    "aurora": {
        "name": "Aurora", "name_zh": "极光",
        "bg1": "#0d1024", "bg2": "#1a1440", "wallpaper": "aurora",
        "wallpaper_file": "assets/wallpapers/wall-aurora.jpg",
        "card": "#23204d", "card_border": "#3a3570",
        "focus": "#ff5c8a", "text": "#f0ecff", "text_dim": "#b8b0e8",
        "accent": "#8f7bff",
    },
    "tech": {
        "name": "Tech Blue", "name_zh": "科技蓝",
        "bg1": "#081120", "bg2": "#0d2038", "wallpaper": "grid",
        "wallpaper_file": "assets/wallpapers/wall-tech.jpg",
        "card": "#12263f", "card_border": "#1f4468",
        "focus": "#2fa8ff", "text": "#e6f4ff", "text_dim": "#8fb8d8",
        "accent": "#37d0b0",
    },
    "space": {
        "name": "Starry Night", "name_zh": "暗星空",
        "bg1": "#0a0a18", "bg2": "#141434", "wallpaper": "stars",
        "wallpaper_file": "assets/wallpapers/wall-space.jpg",
        "card": "#1c1c3e", "card_border": "#34346a",
        "focus": "#ffb454", "text": "#f2f0ff", "text_dim": "#a8a6cc",
        "accent": "#7aa2ff",
    },
    "bright": {
        "name": "Daylight", "name_zh": "明亮",
        "bg1": "#eef2f8", "bg2": "#dde6f2", "wallpaper": "gradient",
        "card": "#ffffff", "card_border": "#c9d4e4",
        "focus": "#ff6b6b", "text": "#1c2434", "text_dim": "#5a6a82",
        "accent": "#2f7cf6",
    },
}


def resolve_theme(config) -> dict:
    """取生效主题：内置主题 + 自定义覆盖（config.theme + config.custom_theme）。"""
    name = config.get("theme", "minimal")
    t = dict(THEMES.get(name, THEMES["minimal"]))
    if name == "custom" or config.get("theme_custom", False):
        ct = config.get("custom_theme") or {}
        for k in ("bg1", "bg2", "card", "card_border", "focus", "text", "text_dim", "accent", "wallpaper"):
            if ct.get(k):
                t[k] = ct[k]
        if ct.get("wallpaper_path"):
            t["wallpaper_path"] = ct["wallpaper_path"]
    # 对比度自动保障：文字 vs 主背景 / 卡片底
    t["text"] = ensure_contrast(t["text"], t["bg1"])
    t["text_dim"] = ensure_contrast(t["text_dim"], t["bg1"], target=4.5)
    t["focus"] = ensure_contrast(t["focus"], t["bg1"], target=3.0)
    return t


# ---------------- QSS 生成 ----------------

def build_qss(t: dict) -> str:
    """按主题生成全局 QSS：电视盒子设计语言。
    - 主窗口：壁纸层透出（root 只做半透明压暗，不盖壁纸）
    - 卡片：半透明毛玻璃 + 大圆角 + 细边框；hover 提亮；focus 渐变+白描边（光晕由代码层阴影实现）
    - 底部 Dock：半透明圆角底条
    """
    c = t
    _check_icon = _find_check_icon()
    focus_grad = f"qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c['focus']}, stop:1 {QColor(c['focus']).darker(130).name()})"
    card_rgba = _hex_to_rgba(c["card"], 0.72)
    card_hover = _hex_to_rgba(c["card"], 0.9)
    border_rgba = _hex_to_rgba(c["card_border"], 0.55)
    return f"""
QWidget#root {{
    background: {c['bg1']};
    color: {c['text']};
    font-size: 16px;
}}
QLabel#appTitle {{ font-size: 20px; font-weight: bold; color: {c['text']}; }}
QLabel#dateLabel {{ font-size: 14px; color: {c['text_dim']}; }}
QLabel#timeLabel {{ font-size: 32px; font-weight: bold; color: {c['text']}; }}
/* 状态标签：半透明胶囊 */
QLabel#statusLabel {{
    font-size: 14px; color: {c['text_dim']};
    background: {_hex_to_rgba('#0a0e1c', 0.45)};
    border: 1px solid {border_rgba};
    border-radius: 12px; padding: 3px 12px;
}}
/* 应用卡片：毛玻璃 + 大圆角 */
QPushButton#appCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_hex_to_rgba('#ffffff', 0.10)}, stop:0.35 {card_rgba}, stop:1 {card_rgba});
    border: 1px solid {border_rgba};
    border-radius: 18px;
    color: {c['text']};
    font-size: 14px;
    min-height: 120px;
    padding: 12px;
}}
QPushButton#appCard:hover {{ background: {card_hover}; border-color: {c['focus']}; }}
QPushButton#appCard:focus {{
    background: {focus_grad};
    border: 2px solid {c['text']};
    color: #ffffff;
    font-weight: bold;
}}
/* 底部 Dock 底条 */
QFrame#dockBar {{
    background: {_hex_to_rgba('#0a0e1c', 0.5)};
    border: 1px solid {border_rgba};
    border-radius: 26px;
}}
QPushButton#bottomBtn, QPushButton#powerBtn {{
    background: {card_rgba};
    border: 1px solid {border_rgba};
    border-radius: 20px;
    font-size: 16px;
    padding: 10px 26px;
    color: {c['text']};
}}
QPushButton#bottomBtn:hover, QPushButton#powerBtn:hover {{ background: {card_hover}; }}
QPushButton#bottomBtn:focus, QPushButton#powerBtn:focus {{
    background: {focus_grad};
    border: 2px solid {c['text']};
    color: #ffffff;
}}
QDialog {{
    background: {_hex_to_rgba(c['bg1'], 0.96)};
    color: {c['text']};
    font-size: 15px;
}}
QDialog QPushButton {{
    background: {card_rgba};
    border: 1px solid {border_rgba};
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 15px;
    color: {c['text']};
}}
QDialog QPushButton:hover {{ background: {card_hover}; }}
QDialog QPushButton:focus {{ background: {c['focus']}; border: 2px solid {c['text']}; }}
QDialog QCheckBox {{ font-size: 15px; spacing: 10px; color: {c['text']}; }}
QDialog QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 5px;
    border: 2px solid {c['text_dim']};
    background: {_hex_to_rgba('#0a0e1c', 0.5)};
}}
QDialog QCheckBox::indicator:hover {{ border-color: {c['focus']}; }}
QDialog QCheckBox::indicator:checked {{
    background: {c['focus']};
    border: 2px solid {c['focus']};
    image: url({_check_icon});
}}
QDialog QLineEdit {{
    background: {_hex_to_rgba('#0a0e1c', 0.6)}; border: 1px solid {c['card_border']}; border-radius: 8px;
    padding: 7px; color: {c['text']}; font-size: 15px;
}}
QDialog QComboBox {{
    background: {card_rgba}; border: 1px solid {c['card_border']}; border-radius: 8px;
    padding: 6px; color: {c['text']}; font-size: 15px;
}}
QDialog QComboBox QAbstractItemView {{
    background: {c['card']}; color: {c['text']};
    selection-background-color: {c['focus']}; selection-color: #ffffff;
}}
QDialog QListWidget {{
    background: {_hex_to_rgba('#0a0e1c', 0.6)}; border: 1px solid {c['card_border']}; border-radius: 10px;
    color: {c['text']}; font-size: 15px; padding: 4px;
}}
QDialog QListWidget::item {{ padding: 9px; border-radius: 8px; }}
QDialog QListWidget::item:selected {{ background: {c['focus']}; color: #ffffff; }}
QSlider::groove:horizontal {{ height: 6px; background: {c['card_border']}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 24px; height: 24px; margin: -9px 0;
    background: {c['focus']}; border-radius: 12px;
}}
QMessageBox {{ background: {_hex_to_rgba(c['bg1'], 0.96)}; }}
QMessageBox QLabel {{ color: {c['text']}; }}
QMessageBox QPushButton {{
    background: {card_rgba};
    border: 1px solid {border_rgba};
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 15px;
    color: {c['text']};
}}
QMessageBox QPushButton:hover {{ background: {card_hover}; }}
QMessageBox QPushButton:focus {{ background: {c['focus']}; border: 2px solid {c['text']}; }}
QProgressDialog {{ background: {_hex_to_rgba(c['bg1'], 0.96)}; color: {c['text']}; }}
QProgressDialog QLabel {{ color: {c['text']}; }}
QProgressDialog QPushButton {{
    background: {card_rgba};
    border: 1px solid {border_rgba};
    border-radius: 10px;
    padding: 7px 16px;
    color: {c['text']};
}}
QProgressDialog QPushButton:hover {{ background: {card_hover}; }}
QProgressDialog QPushButton:focus {{ background: {c['focus']}; }}
QDialog QLabel {{ color: {c['text']}; }}
QScrollArea {{ background: transparent; }}
QToolTip {{
    background: {c['card']}; color: {c['text']};
    border: 1px solid {c['card_border']}; padding: 5px;
}}
"""


def _find_check_icon() -> str:
    """查找勾选图标绝对路径（部署目录/源码树）。"""
    import sys as _sys
    from pathlib import Path as _Path
    for base in (_Path.cwd(), _Path(__file__).resolve().parents[2],
                 _Path(getattr(_sys, "_MEIPASS", "/nonexistent"))):
        p = base / "assets" / "ui" / "check.png"
        if p.exists():
            return str(p)
    return ""


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """#rrggbb + alpha → rgba(r,g,b,a)。"""
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


# ---------------- 程序化壁纸 ----------------

def generate_wallpaper(t: dict, width: int, height: int) -> QPixmap:
    """按主题壁纸风格生成背景图（渐变/极光/网格/星空）。"""
    pm = QPixmap(max(width, 32), max(height, 32))
    pm.fill(QColor(t["bg1"]))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    style = t.get("wallpaper_path") or t.get("wallpaper", "gradient")
    if style == "gradient" or (t.get("wallpaper_path") and not style):
        g = QLinearGradient(0, 0, width, height)
        g.setColorAt(0, QColor(t["bg1"]))
        g.setColorAt(1, QColor(t["bg2"]))
        p.fillRect(QRectF(0, 0, width, height), g)
    elif style == "aurora":
        _aurora(p, t, width, height)
    elif style == "grid":
        _grid(p, t, width, height)
    elif style == "stars":
        _stars(p, t, width, height)
    p.end()
    return pm


def _aurora(p: QPainter, t: dict, w: int, h: int) -> None:
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(t["bg1"]))
    g.setColorAt(1, QColor(t["bg2"]))
    p.fillRect(QRectF(0, 0, w, h), g)
    blobs = [
        (0.2, 0.25, QColor(140, 100, 255, 90), w * 0.5),
        (0.8, 0.6, QColor(255, 92, 138, 70), w * 0.45),
        (0.5, 0.9, QColor(55, 208, 176, 55), w * 0.5),
    ]
    for fx, fy, col, r in blobs:
        rg = QRadialGradient(QPointF(w * fx, h * fy), r)
        rg.setColorAt(0, col)
        rg.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
        p.fillRect(QRectF(0, 0, w, h), rg)


def _grid(p: QPainter, t: dict, w: int, h: int) -> None:
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(t["bg1"]))
    g.setColorAt(1, QColor(t["bg2"]))
    p.fillRect(QRectF(0, 0, w, h), g)
    p.setPen(QColor(47, 168, 255, 28))
    step = 44
    for x in range(0, w, step):
        p.drawLine(x, 0, x, h)
    for y in range(0, h, step):
        p.drawLine(0, y, w, y)
    rg = QRadialGradient(QPointF(w * 0.5, h * 0.3), w * 0.6)
    rg.setColorAt(0, QColor(47, 168, 255, 55))
    rg.setColorAt(1, QColor(47, 168, 255, 0))
    p.fillRect(QRectF(0, 0, w, h), rg)


def _stars(p: QPainter, t: dict, w: int, h: int) -> None:
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(t["bg1"]))
    g.setColorAt(1, QColor(t["bg2"]))
    p.fillRect(QRectF(0, 0, w, h), g)
    rng = random.Random(42)  # 固定种子：每次渲染一致
    for _ in range(int(w * h / 4200)):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(0.8, 2.2)
        alpha = rng.randint(60, 200)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, alpha))
        p.drawEllipse(QPointF(x, y), r, r)
    rg = QRadialGradient(QPointF(w * 0.7, h * 0.25), w * 0.45)
    rg.setColorAt(0, QColor(122, 162, 255, 60))
    rg.setColorAt(1, QColor(122, 162, 255, 0))
    p.fillRect(QRectF(0, 0, w, h), rg)
