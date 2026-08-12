"""主窗口：状态栏 + 应用网格 + 底部按钮 + 设置/市场弹窗 + 遥控器桥接 + 看门狗。

输入设计（修订版开发文档 1.1）：
- 统一按键路径：真实键盘事件 与 遥控器合成事件 都走 QApplication 级事件过滤器
- 遥控器 HOME 态 grab 时：按键由 remote 模块合成 QKeyEvent 注入
- 遥控器 grab 失效时：按键自然到达 Qt，走同一条事件过滤器路径
  → 两种状态行为完全一致，不再出现"只有按钮能聚焦"的退化
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QEvent, QObject, QSize, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QKeyEvent, QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
                             QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QProgressDialog,
                             QPushButton, QRadioButton, QScrollArea, QSlider, QVBoxLayout,
                             QWidget)

from ..apps import App, AppManager
from ..config import LOG_DIR
from ..displays import label as disp_label
from ..displays import list_connectors
from ..i18n import format_date, tr
from ..theme import (build_qss, ensure_contrast, generate_wallpaper,
                     resolve_theme, THEMES)
from ..remote import Remote
from ..waydroid import Waydroid

logger = logging.getLogger("tview.ui")


# 遥控器线程 → Qt 主线程的信号桥
class RemoteBridge(QObject):
    key = pyqtSignal(str)
    longpress_back = pyqtSignal()
    device_lost = pyqtSignal()
    remote_state = pyqtSignal(bool)
    apps_loaded = pyqtSignal(list)


class TViewCard(QPushButton):
    """应用卡片：聚焦时浮现主题色光晕（电视盒子焦点感）。

    不放大 icon/几何（避免 layout 重排跳动），聚焦反馈 = 白描边渐变(QSS) + 光晕阴影(代码)。
    """

    def __init__(self, app: App, focus_color: str = "#e94560", parent=None):
        super().__init__(parent)
        self.app = app
        self.focus_color = focus_color
        self.setObjectName("appCard")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        color = QColor(self.focus_color)
        color.setAlpha(200)
        self._shadow.setColor(color)
        self._shadow.setBlurRadius(42)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._shadow.setBlurRadius(0)


class MainWindow(QWidget):
    """启视·TVIEW 主窗口。"""

    def __init__(self, config, waydroid: Waydroid, app_mgr: AppManager, remote: Remote):
        super().__init__()
        self.config = config
        self.waydroid = waydroid
        self.app_mgr = app_mgr
        self.remote = remote
        self.apps: list[App] = []
        self.focused_index = 0  # 焦点索引（_focusables 列表中的位置），自管理不依赖平台焦点
        self._back_press_time: float | None = None  # Qt 路径长按返回检测
        self._recording_cb = None  # 遥控器映射录制回调（KeyMapDialog 注册，eventFilter 捕获后调用）

        self.bridge = RemoteBridge()
        self.bridge.key.connect(self.on_remote_key)
        self.bridge.longpress_back.connect(self.on_longpress_back)
        self.bridge.device_lost.connect(self.on_device_lost)
        self.bridge.remote_state.connect(self.on_remote_state)
        self.bridge.apps_loaded.connect(self.on_apps_loaded)
        remote.on_key = self.bridge.key.emit
        remote.on_longpress_back = self.bridge.longpress_back.emit
        remote.on_device_lost = self.bridge.device_lost.emit
        remote.on_remote_state = self.bridge.remote_state.emit

        self._build_ui()
        self._start_timers()
        self._dock_hide()
        self._sync_autostart()  # 启动时按配置补写/清理自启文件（默认开但文件可能从未写过）
        self._start_vnc()  # kiosk 模式下启动 VNC 远程（wayvnc）
        if remote.keyd_mode:
            # keyd 模式下无 evdev 设备上报，直接标记在线。
            # 注意：必须在 _build_ui() 之后 emit，否则 on_remote_state 同步执行时
            # self.remote_label 还不存在，会抛 AttributeError（启动崩溃）。
            self.bridge.remote_state.emit(True)

        # 全局事件过滤器：统一处理 回车/返回/主页（真实键盘 + 遥控器合成事件）
        QApplication.instance().installEventFilter(self)

    # ---------------- UI 构建 ----------------
    def _build_ui(self) -> None:
        self.setWindowTitle(tr("app_title"))
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)  # QWidget 子类需此属性才绘制 QSS 背景
        # 壁纸背景层（主题驱动，程序化生成）
        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(self.rect())
        self.bg_label.lower()
        self.apply_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 12, 24, 16)
        root.setSpacing(10)

        # 顶部状态栏
        self.status_bar = QWidget()
        sb = QHBoxLayout(self.status_bar)
        sb.setContentsMargins(4, 0, 4, 0)
        self.app_title = QLabel(tr("app_title"))
        self.date_label = QLabel()
        self.net_label = QLabel(tr("network_checking"))
        self.remote_label = QLabel(tr("remote_connecting"))
        self.wd_label = QLabel(tr("wd_status"))
        self.time_label = QLabel()
        self.app_title.setObjectName("appTitle")
        self.date_label.setObjectName("dateLabel")
        self.remote_label.setObjectName("statusLabel")
        self.wd_label.setObjectName("statusLabel")
        self.net_label.setObjectName("statusLabel")
        self.time_label.setObjectName("timeLabel")
        self.date_label.setStyleSheet("font-size:16px;color:#aab4cc;")
        self.remote_label.setStyleSheet("font-size:15px;color:#8ab4f8;background:rgba(255,255,255,0.06);border-radius:10px;padding:2px 10px;")
        self.wd_label.setStyleSheet("font-size:15px;color:#8ab4f8;background:rgba(255,255,255,0.06);border-radius:10px;padding:2px 10px;")
        self.net_label.setStyleSheet("font-size:15px;color:#8ab4f8;background:rgba(255,255,255,0.06);border-radius:10px;padding:2px 10px;")
        self.time_label.setStyleSheet("font-size:32px;font-weight:bold;color:#ffffff;")
        sb.addWidget(self.app_title)
        sb.addSpacing(12)
        sb.addWidget(self.date_label)
        sb.addStretch(1)
        sb.addWidget(self.remote_label)
        sb.addSpacing(14)
        sb.addWidget(self.wd_label)
        sb.addSpacing(14)
        sb.addWidget(self.net_label)
        sb.addStretch(1)
        sb.addWidget(self.time_label)
        root.addWidget(self.status_bar)

        # 应用网格 + 加载提示（可滚动，防止应用多时溢出挤掉底部按钮）
        self.grid_area = QWidget()
        ga = QVBoxLayout(self.grid_area)
        ga.setContentsMargins(0, 0, 0, 0)
        self.loading_label = QLabel(tr("loading_apps"))
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("font-size:20px;color:#888;")
        ga.addWidget(self.loading_label)
        # Waydroid 离线提示（Linux 应用不受影响）
        self.waydroid_hint = QLabel(tr("waydroid_hint"))
        self.waydroid_hint.setAlignment(Qt.AlignCenter)
        self.waydroid_hint.setStyleSheet("font-size:16px;color:#f0a35e;background:#3a2a1a;border-radius:6px;padding:8px;")
        self.waydroid_hint.hide()
        ga.addWidget(self.waydroid_hint)
        self.grid_wrap = QWidget()
        self.grid = QGridLayout(self.grid_wrap)
        self.grid.setSpacing(14)
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.NoFrame)
        # 关键：viewport 默认白色背景会盖住壁纸，必须透明
        self.grid_scroll.viewport().setAutoFillBackground(False)
        self.grid_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea > QWidget > QWidget{background:transparent;}")
        self.grid_scroll.setWidget(self.grid_wrap)
        ga.addWidget(self.grid_scroll, 1)
        root.addWidget(self.grid_area, 1)

        # 底部 Dock：半透明底条包裹 4 个按钮
        self.dock_bar = QFrame()
        self.dock_bar.setObjectName("dockBar")
        dock = QHBoxLayout(self.dock_bar)
        dock.setContentsMargins(20, 12, 20, 12)
        dock.setSpacing(18)
        self.btn_settings = self._bottom_button(tr("settings"), self.open_settings)
        self.btn_market = self._bottom_button(tr("market"), self.open_market)
        self.btn_exit = self._bottom_button(tr("power_exit"), self.exit_box)
        self.btn_power = self._bottom_button(tr("power_menu_title"), self._power_menu)
        dock.addWidget(self.btn_settings)
        dock.addWidget(self.btn_market)
        dock.addWidget(self.btn_exit)
        dock.addWidget(self.btn_power)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self.dock_bar)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.showFullScreen()  # 最后再全屏：避免 resize 事件打断布局初始化

    def apply_theme(self) -> None:
        """应用当前主题：生成全局 QSS + 更新 palette + 重绘壁纸（即时生效）。"""
        t = resolve_theme(self.config)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(t))
            from PyQt5.QtGui import QColor, QPalette
            pal = app.palette()
            for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                         QPalette.HighlightedText, QPalette.ToolTipText):
                pal.setColor(role, QColor(t["text"]))
            pal.setColor(QPalette.PlaceholderText, QColor(t["text_dim"]))
            app.setPalette(pal)
        if hasattr(self, "bg_label"):
            pm = self._load_wallpaper(t)
            self.bg_label.setPixmap(pm)
            self.bg_label.setGeometry(self.rect())
            self.bg_label.lower()

    def _load_wallpaper(self, t: dict) -> QPixmap:
        """壁纸优先级：自定义图片 > 主题默认图片 > 程序化生成。"""
        path = t.get("wallpaper_path") or ""
        if not (path and Path(path).exists()):
            path = self._find_wallpaper_file(t.get("wallpaper_file") or "")
        if path and Path(path).exists():
            pm = QPixmap(path)
            if not pm.isNull():
                return pm.scaled(self.width() or 1280, self.height() or 720,
                                 Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        return generate_wallpaper(t, self.width() or 1280, self.height() or 720)

    @staticmethod
    def _find_wallpaper_file(rel: str) -> str:
        """按相对路径找主题壁纸：部署目录/源码树/打包目录。"""
        if not rel:
            return ""
        import sys as _sys
        for base in (Path.cwd(),
                     Path(__file__).resolve().parents[2],
                     Path(getattr(_sys, "_MEIPASS", "/nonexistent"))):
            p = base / rel
            if p.exists():
                return str(p)
        return ""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "bg_label") and self.bg_label.pixmap() is not None:
            t = resolve_theme(self.config)
            self.bg_label.setPixmap(self._load_wallpaper(t))
            self.bg_label.setGeometry(self.rect())
            self.bg_label.lower()


        # Toast（短暂提示）
        self.toast = QLabel("", self)
        self.toast.setAlignment(Qt.AlignCenter)
        self.toast.setStyleSheet(
            "background:rgba(0,0,0,180);color:#fff;font-size:18px;border-radius:8px;padding:12px 24px;"
        )
        self.toast.hide()

    def _bottom_button(self, text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("bottomBtn")
        btn.setFocusPolicy(Qt.StrongFocus)
        btn.setMinimumWidth(150)  # 统一宽度，避免文字长度不一导致大小不齐
        btn.clicked.connect(slot)
        return btn

    def _make_card(self, app: App) -> TViewCard:
        """生成应用卡片（StrongFocus，可被 Qt 焦点遍历和事件过滤器激活）。"""
        btn = TViewCard(app, focus_color=resolve_theme(self.config)["focus"])
        if app.icon and Path(app.icon).exists():
            btn.setIcon(QIcon(app.icon))
            btn.setIconSize(QSize(68, 68))
        name = app.name if len(app.name) <= 8 else app.name[:7] + "…"
        btn.setText(name)
        btn.clicked.connect(lambda _, a=app: self.launch_app(a))
        return btn

    def render_grid(self) -> None:
        """原地清空重建网格（标准 clearLayout 模式，不换容器/不调 setWidget）。

        要点：旧卡片先 setParent(None) 解绑再 deleteLater，避免 layout item 悬空；
        QScrollArea.setWidget 换容器在 offscreen 下会把新 grid 清空（勿用）。
        """
        try:
            cols = max(2, min(6, int(self.config.get("columns", 3))))
            while self.grid.count():
                item = self.grid.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            for i, app in enumerate(self.apps):
                self.grid.addWidget(self._make_card(app), i // cols, i % cols)
            self.grid.setRowStretch((len(self.apps) - 1) // cols + 1, 1)
            # 恢复焦点：优先原卡片，否则按 focused_index，再退到第一张
            if self.focused_index < len(self.apps) and self.grid.count():
                self.grid.itemAt(self.focused_index).widget().setFocus()
                self.grid_scroll.ensureWidgetVisible(self.grid.itemAt(self.focused_index).widget(), 0, 0)
            elif self.grid.count():
                self.grid.itemAt(0).widget().setFocus()
        except Exception as e:
            logger.error("重建网格失败: %s", e)

    def _focusables(self) -> list:
        """全部可聚焦控件：网格卡片（行优先） + 底部按钮。"""
        items = []
        for i in range(self.grid.count()):
            w = self.grid.itemAt(i).widget()
            if w is not None:
                items.append(w)
        items.append(self.btn_settings)
        items.append(self.btn_market)
        items.append(self.btn_exit)
        items.append(self.btn_power)
        return items

    def _nav_grid(self, key: int) -> None:
        """方向键导航：网格 + 底部按钮行模型。
        - 向下：最后一行卡片 → 设置按钮 → 应用下载按钮 → 循环
        - 向上：按钮行 → 最后一行卡片；顶部停在第一行
        - 左右：横向移动，边界循环
        """
        cards = []
        for i in range(self.grid.count()):
            w = self.grid.itemAt(i).widget()
            if w is not None:
                cards.append(w)
        buttons = [self.btn_settings, self.btn_market, self.btn_exit, self.btn_power]
        items = cards + buttons
        if not items:
            return
        cols = max(2, min(6, int(self.config.get("columns", 3))))
        n = len(cards)
        idx = self.focused_index
        if key == Qt.Key_Down:
            if idx < n:
                idx += cols
                if idx >= n:
                    idx = n  # 最后一行 → 设置按钮
            else:
                # 按钮行内循环：设置→应用下载→设置
                idx = n + ((idx - n + 1) % len(buttons))
        elif key == Qt.Key_Up:
            if idx >= n:
                idx = n - 1  # 按钮行 → 最后一张卡片
            else:
                idx -= cols
                if idx < 0:
                    idx = 0  # 顶部停在第一行
        elif key == Qt.Key_Right:
            idx += 1
            if idx >= len(items):
                idx = 0
        elif key == Qt.Key_Left:
            idx -= 1
            if idx < 0:
                idx = len(items) - 1
        self.focused_index = idx
        items[idx].setFocus()
        # 滚动到焦点卡片可见（应用多时网格可滚动）
        if hasattr(self, "grid_scroll") and idx < n:
            self.grid_scroll.ensureWidgetVisible(items[idx], 0, 0)

    # ---------------- 全局输入（事件过滤器） ----------------
    def eventFilter(self, obj, ev):
        """统一处理：方向导航 / 回车激活 / 返回键 / 设置键 / 主页键 / 长按返回。
        keyd 模式下这是唯一输入路径；非 keyd 模式作为 grab 失效时的兜底。"""
        if ev.type() == QEvent.KeyPress:
            k = ev.key()
            w = QApplication.focusWidget()
            if isinstance(w, QLineEdit):
                return False  # 文本输入场景不拦截
            # 遥控器映射录制态：捕获按键交给录制回调（KeyMapDialog）
            if self._recording_cb is not None:
                cb = self._recording_cb
                self._recording_cb = None
                cb(k)
                return True
            # 自定义遥控器映射（用户设置优先于系统默认）
            kmap = self.config.get("remote_keymap") or {}
            action = kmap.get(str(k))
            if action:
                if action != "ignore":
                    self._dispatch_mapped(action)
                return True
            if k in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                modal = QApplication.activeModalWidget()
                if modal is not None:
                    # 模态框内：滑块聚焦时按上下键要离开滑块（左右键留给滑块调值）
                    w = QApplication.focusWidget()
                    if isinstance(w, QSlider) and k in (Qt.Key_Up, Qt.Key_Down):
                        if k == Qt.Key_Down:
                            w.focusNextChild()
                        else:
                            w.focusPreviousChild()
                        return True
                    return False  # 其他情况交给对话框
                self._nav_grid(k)
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                # 优先用事件目标（obj），离屏/无焦点环境更可靠
                w = obj if isinstance(obj, QWidget) else QApplication.focusWidget()
                if w is not None and getattr(w, "app", None) is not None:
                    self.launch_app(w.app)
                elif isinstance(w, QPushButton):
                    w.click()
                elif self.apps:
                    # 平台焦点不可用时回退到自管理索引
                    self.focused_index %= len(self.apps)
                    self.launch_app(self.apps[self.focused_index])
                return True
            if k in (Qt.Key_Back, Qt.Key_Backspace):
                self._back_press_time = time.monotonic()
                if k == Qt.Key_Back:
                    # 返回键：关弹窗或回主页
                    modal = QApplication.activeModalWidget()
                    if modal is not None:
                        modal.reject()
                    else:
                        self.show_home()
                else:
                    # 退格键 = 本遥控器的设置键：有弹窗则关闭，无弹窗则打开设置
                    modal = QApplication.activeModalWidget()
                    if modal is not None:
                        modal.reject()
                    else:
                        self.open_settings()
                return True
            if k == Qt.Key_Home:
                modal = QApplication.activeModalWidget()
                if modal is not None:
                    modal.reject()
                self.show_home()
                return True
            if k in (Qt.Key_VolumeUp, Qt.Key_VolumeDown) and self.config.get("input_keyd", False) is False:
                # 非 keyd 模式兜底：音量键直达 wpctl
                self._volume("volume_up" if k == Qt.Key_VolumeUp else "volume_down")
                return True
        elif ev.type() == QEvent.KeyRelease and ev.key() == Qt.Key_Back:
            # Qt 路径长按返回检测（HOME 态；APP 态无焦点收不到，接受简化）
            if self._back_press_time and (time.monotonic() - self._back_press_time) >= self.remote.longpress_ms / 1000:
                self.on_longpress_back()
            self._back_press_time = None
            return True
        return False

    # ---------------- 遥控器 ----------------
    def on_remote_key(self, action: str) -> None:
        """遥控器动作：导航键合成 QKeyEvent 注入（与真实键盘同路径）；电源/音量直接处理。"""
        keymap = {
            "up": Qt.Key_Up, "down": Qt.Key_Down, "left": Qt.Key_Left,
            "right": Qt.Key_Right, "enter": Qt.Key_Return,
            "back": Qt.Key_Back, "home": Qt.Key_Home,
        }
        if action in keymap:
            ev = QKeyEvent(QEvent.KeyPress, keymap[action], Qt.NoModifier)
            target = QApplication.focusWidget() or self
            QApplication.sendEvent(target, ev)
        elif action == "power":
            self._power_menu()
        elif action == "settings":
            self.open_settings()
        elif action in ("volume_up", "volume_down"):
            self._volume(action)
        elif action == "menu":
            logger.info("菜单键：打开应用下载")
            self.open_market()

    def on_longpress_back(self) -> None:
        """长按返回 3 秒：回主页 + 隐藏 Waydroid 窗口（尽力而为）。"""
        logger.info("长按返回：回主页")
        self.remote.set_state("HOME")
        self._hide_waydroid_window()
        self.show_home()

    def _hide_waydroid_window(self) -> None:
        """回主页：把焦点切回 TVIEW。
        kiosk（labwc）：wlrctl focus tview（app_id 匹配，已实测）。
        桌面（GNOME）：wlrctl minimize（wlroots 系合成器；无则仅记录）。"""
        if self.config.mock or not shutil.which("wlrctl"):
            return
        try:
            if self._is_kiosk():
                subprocess.run(["wlrctl", "window", "focus", "tview"], timeout=5,
                               capture_output=True)
                logger.info("焦点已切回 TVIEW")
            else:
                subprocess.run(["wlrctl", "window", "minimize"], timeout=5,
                               capture_output=True)
                logger.info("已请求最小化 Waydroid 窗口")
        except Exception as e:
            logger.warning("隐藏 Waydroid 窗口失败: %s", e)

    def on_remote_state(self, ok: bool) -> None:
        """遥控器设备在位状态显示（未检测到=无权限或未插接收器）。"""
        label = getattr(self, "remote_label", None)
        if label is None:
            return  # UI 尚未构建完成（启动早期信号），防御性跳过
        base = "font-size:15px;background:rgba(255,255,255,0.06);border-radius:10px;padding:2px 10px;"
        if ok:
            label.setText(tr("remote_online"))
            label.setStyleSheet(base + "color:#7ee787;")
        else:
            label.setText(tr("remote_offline"))
            label.setStyleSheet(base + "color:#f85149;")

    def on_device_lost(self) -> None:
        """遥控器掉线提示。"""
        self._toast(tr("toast_remote_lost"))

    # ---------------- 应用加载（异步 + 空列表自动重试） ----------------
    def refresh_apps(self) -> None:
        """异步刷新应用列表（waydroid app list 可能耗时 30s，不能阻塞 UI）。"""
        self.loading_label.show()
        self.loading_label.setText(tr("loading_apps"))
        threading.Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self) -> None:
        try:
            apps = self.app_mgr.refresh()
        except Exception as e:
            logger.error("加载应用失败: %s", e)
            apps = []
        self.bridge.apps_loaded.emit(apps)

    def on_apps_loaded(self, apps: list) -> None:
        self.apps = apps
        # Waydroid 离线提示（Linux 应用不受影响）
        self.waydroid_hint.setVisible(not self.app_mgr.waydroid_ok)
        if apps:
            self.loading_label.hide()
        else:
            self.loading_label.setText(tr("retry_apps"))
        self.render_grid()

    def _retry_empty(self) -> None:
        """空列表或 Waydroid 离线时自动重试（容器解冻/会话恢复后自动补全）。"""
        if self.config.mock:
            return
        if not self.apps or not self.app_mgr.waydroid_ok:
            logger.info("应用列表不完整，自动重试刷新")
            self.refresh_apps()

    # ---------------- 应用启动 ----------------
    def launch_app(self, app: App) -> None:
        """启动应用：安卓走 waydroid，Linux 走 Popen；随后进入 APP 态。"""
        if app.kind == "android":
            ok = self.waydroid.app_launch(app.launch)
            if not ok:
                self._toast(tr("launch_failed").format(app.name))
                return
        else:
            try:
                subprocess.Popen(app.launch, shell=True)
            except Exception as e:
                logger.error("启动 Linux 应用失败: %s", e)
                self._toast(tr("launch_failed").format(app.name))
                return
        logger.info("启动应用: %s (%s)", app.name, app.kind)
        self.remote.set_state("APP")  # 释放 grab，按键流向应用

    def show_home(self) -> None:
        """回到主界面。"""
        self.remote.set_state("HOME")
        self.raise_()
        self.activateWindow()
        self.focused_index = 0
        if self.grid.count():
            self.grid.itemAt(0).widget().setFocus()
        else:
            self.setFocus()

    # ---------------- 定时器 ----------------
    def _start_timers(self) -> None:
        self.t_clock = QTimer(self)
        self.t_clock.timeout.connect(self._update_status)
        self.t_clock.start(1000)
        self._update_status()

        self.t_net = QTimer(self)
        self.t_net.timeout.connect(self._update_network)
        self.t_net.start(30_000)
        self._update_network()

        # 应用空列表重试（15s 一次）
        self.t_retry = QTimer(self)
        self.t_retry.timeout.connect(self._retry_empty)
        self.t_retry.start(15_000)

        # Waydroid 状态轮询（15s）+ 初始刷新
        self.t_wd = QTimer(self)
        self.t_wd.timeout.connect(self._update_wd_status)
        self.t_wd.start(15_000)
        self._update_wd_status()

        # U盘 APK 检测（5s）
        self._known_usb_apks: set = set()
        self.t_usb = QTimer(self)
        self.t_usb.timeout.connect(self._scan_usb_apks)
        self.t_usb.start(5_000)
        self._scan_usb_apks()

        # 看门狗：30s 检测 waydroid，3 次失败重启，3 次重启失败回主界面
        self._wd_fails = 0
        self._wd_restarts = 0
        self.t_wd = QTimer(self)
        self.t_wd.timeout.connect(self._watchdog)
        self.t_wd.start(int(self.config.get("watchdog_interval_s", 30)) * 1000)

        # 网格自愈：某些平台（offscreen/无窗口系统）QScrollArea 会清空 layout items，
        # 2s 检查一次，空则重建（真实环境 grid 不空，零开销）
        self.t_grid = QTimer(self)
        self.t_grid.timeout.connect(self._ensure_grid)
        self.t_grid.start(2000)

    def _ensure_grid(self) -> None:
        """防御：应用列表非空但网格意外为空时重建（异常场景自愈）。"""
        if self.apps and self.grid.count() == 0:
            logger.warning("网格为空，自动重建（%d 个应用）", len(self.apps))
            self.render_grid()

    def _update_status(self) -> None:
        now = datetime.now()
        self.date_label.setText(format_date(now))
        self.time_label.setText(now.strftime("%H:%M"))

    def _update_network(self) -> None:
        """读 /sys/class/net 判断有线/WiFi/断开（简单可靠）。"""
        try:
            states = []
            for dev in Path("/sys/class/net").iterdir():
                if dev.name == "lo":
                    continue
                op = (dev / "operstate").read_text().strip()
                if op == "up":
                    states.append(tr("network_wifi") if (dev / "wireless").exists() else tr("network_wired"))
            self.net_label.setText(states[0] if states else tr("network_off"))
            if not states:
                self._ping_check()
        except Exception:
            self.net_label.setText(tr("network_off"))

    def _ping_check(self) -> None:
        """离线时 ping 探测（目标 223.5.5.5，可配置）。"""
        target = self.config.get("ping_target", "223.5.5.5")
        if self.config.mock:
            return
        try:
            r = subprocess.run(["ping", "-c", "1", "-W", "2", target],
                               capture_output=True, timeout=4)
            if r.returncode == 0:
                self.net_label.setText(tr("network_ok"))
        except Exception:
            pass

    def _update_wd_status(self) -> None:
        """Waydroid 状态标签（三态，设置可关，默认显示）。"""
        if not self.config.get("wd_status_show", True):
            self.wd_label.hide()
            return
        self.wd_label.show()
        base = "font-size:15px;background:rgba(255,255,255,0.06);border-radius:10px;padding:2px 10px;"
        if self.config.mock:
            self.wd_label.setText(tr("wd_mock"))
            self.wd_label.setStyleSheet(base + "color:#7ee787;")
            return
        state = self.waydroid.status_state()
        if state == "running":
            self.wd_label.setText(tr("wd_running"))
            self.wd_label.setStyleSheet(base + "color:#7ee787;")
        elif state == "frozen":
            # 容器被 Android 休眠机制冻结（非故障，启动应用自动唤醒）
            self.wd_label.setText(tr("wd_frozen"))
            self.wd_label.setStyleSheet(base + "color:#f0a35e;")
        elif state == "starting":
            self.wd_label.setText(tr("wd_starting"))
            self.wd_label.setStyleSheet(base + "color:#f0a35e;")
        else:
            self.wd_label.setText(tr("wd_stopped"))
            self.wd_label.setStyleSheet(base + "color:#888;")

    # ---------------- U盘 APK 检测与安装 ----------------
    def _usb_apk_paths(self) -> list:
        """扫描常见 U 盘挂载点下的 APK 文件。"""
        import os
        found = []
        bases = [Path(f"/run/media/{os.environ.get('USER', 'chimingxu')}"), Path("/media")]
        for base in bases:
            if not base.exists():
                continue
            try:
                for vol in base.iterdir():
                    if vol.is_dir():
                        found.extend(p for p in vol.rglob("*.apk") if p.is_file())
            except PermissionError:
                continue
        return found

    def _scan_usb_apks(self) -> None:
        """轮询 U 盘 APK：新发现时提示（菜单键/下载页可安装）。"""
        if self.config.mock:
            return
        try:
            apks = {str(p) for p in self._usb_apk_paths()}
        except Exception:
            return
        new = apks - self._known_usb_apks
        if new:
            for p in sorted(new):
                logger.info("U盘发现 APK: %s", p)
                self._toast(tr("toast_usb_apk").format(Path(p).name))
        self._known_usb_apks = apks

    def open_usb_install(self) -> None:
        """U盘 APK 安装对话框（遥控器全流程）。"""
        dlg = UsbInstallDialog(self.waydroid, self.config, self)
        dlg.exec_()
        self.refresh_apps()

    # ---------------- 设置 / 市场 ----------------
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        dlg.exec_()
        if dlg.changed:
            self.config.save()
            self.render_grid()

    def open_market(self) -> None:
        dlg = MarketDialog(self.waydroid, self.config, self)
        dlg.exec_()
        self.refresh_apps()

    def _dispatch_mapped(self, action: str) -> None:
        """执行自定义映射动作（直接处理，不走事件注入，避免递归）。"""
        nav = {"up": Qt.Key_Up, "down": Qt.Key_Down,
               "left": Qt.Key_Left, "right": Qt.Key_Right}
        if action in nav:
            self._nav_grid(nav[action])
            return
        if action == "enter":
            w = QApplication.focusWidget()
            if w is not None and getattr(w, "app", None) is not None:
                self.launch_app(w.app)
            elif isinstance(w, QPushButton):
                w.click()
            return
        if action == "back":
            modal = QApplication.activeModalWidget()
            if modal is not None:
                modal.reject()
            else:
                self.show_home()
            return
        if action == "home":
            modal = QApplication.activeModalWidget()
            if modal is not None:
                modal.reject()
            self.show_home()
            return
        if action == "settings":
            self.open_settings()
            return
        if action == "menu":
            self.open_market()
            return
        if action in ("volume_up", "volume_down"):
            self._volume(action)
            return
        if action == "power":
            self._power_menu()
            return
        logger.info("映射动作未实现: %s", action)

    def _sync_autostart(self) -> None:
        """启动时同步自启文件与配置：autostart=true 但文件缺失时补写，
        autostart=false 但文件残留时清理。修复"默认开但从未写入"的 BUG。"""
        desktop = Path.home() / ".config/autostart" / "tview.desktop"
        want = bool(self.config.get("autostart", True))
        has = desktop.exists()
        if want and not has:
            logger.info("自启配置开启但文件缺失，启动时补写")
            self._apply_autostart(True)
        elif not want and has:
            logger.info("自启配置关闭但文件残留，启动时清理")
            self._apply_autostart(False)

    def _apply_autostart(self, enabled: bool) -> None:
        """写入/删除 ~/.config/autostart/tview.desktop（开机自启开关，设置里可切换）。"""
        if self.config.mock:
            logger.info("开机自启(%s) - mock", enabled)
            return
        try:
            autostart_dir = Path.home() / ".config/autostart"
            desktop = autostart_dir / "tview.desktop"
            if enabled:
                autostart_dir.mkdir(parents=True, exist_ok=True)
                exe = str(Path("/proc/self/exe").resolve())
                # 源码调试模式（python main.py）下 /proc/self/exe 是解释器，改用脚本真实路径
                if "python" in Path(exe).name.lower():
                    exe = str(Path(sys.argv[0]).resolve())
                desktop.write_text(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    f"Name={tr('app_title')}\n"
                    "Comment=TV box launcher\n"
                    f"Exec={exe} --prod\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n",
                    encoding="utf-8")
                logger.info("开机自启已开启: %s", desktop)
            else:
                if desktop.exists():
                    desktop.unlink()
                    logger.info("开机自启已关闭")
        except Exception as e:
            logger.error("设置开机自启失败: %s", e)

    def _autologin_status(self) -> bool | None:
        """查询 GDM 开机免密状态：True/False；None=无权限或未安装脚本。"""
        script = "/usr/local/sbin/tview-autologin.sh"
        if self.config.mock or not Path(script).exists():
            return None
        try:
            r = subprocess.run(["sudo", "-n", script, "status"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return "enabled" in r.stdout
        except Exception as e:
            logger.warning("查询开机免密状态失败: %s", e)
        return None

    def _autologin_session(self) -> str:
        """查询当前 autologin 会话：tview / gnome（无权限时默认 gnome）。"""
        script = "/usr/local/sbin/tview-autologin.sh"
        if self.config.mock or not Path(script).exists():
            return "gnome"
        try:
            r = subprocess.run(["sudo", "-n", script, "status"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "session=tview" in r.stdout:
                return "tview"
        except Exception as e:
            logger.warning("查询 autologin 会话失败: %s", e)
        return "gnome"

    def _apply_autologin(self, enabled: bool) -> tuple[bool, str]:
        """设置 GDM 开机免密（需要 NOPASSWD 白名单执行 /usr/local/sbin/tview-autologin.sh）。"""
        if self.config.mock:
            logger.info("开机免密(%s) - mock", enabled)
            return True, ""
        script = "/usr/local/sbin/tview-autologin.sh"
        if not Path(script).exists():
            return False, tr("autologin_no_perm")
        try:
            r = subprocess.run(["sudo", "-n", script, "on" if enabled else "off"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                logger.info("开机免密已%s", "开启" if enabled else "关闭")
                return True, ""
            return False, (r.stderr or r.stdout or "unknown").strip()
        except Exception as e:
            return False, str(e)

    def _apply_mode(self, mode: str) -> tuple[bool, str]:
        """切换运行模式（L1/L2 整合）：tview=盒子模式 / gnome=桌面模式 / off=正常登录。
        本质是 autologin 会话切换（tview-autologin.sh on <session>）。"""
        if self.config.mock:
            logger.info("运行模式(%s) - mock", mode)
            return True, ""
        script = "/usr/local/sbin/tview-autologin.sh"
        if not Path(script).exists():
            return False, tr("autologin_no_perm")
        try:
            if mode == "off":
                cmd = ["sudo", "-n", script, "off"]
            else:
                cmd = ["sudo", "-n", script, "on", mode]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                logger.info("运行模式已切换: %s", mode)
                self.config.set("mode", mode)
                return True, ""
            return False, (r.stderr or r.stdout or "unknown").strip()
        except Exception as e:
            return False, str(e)

    # ---------------- 系统操作 ----------------
    def _volume(self, action: str) -> None:
        """音量键：调整 PipeWire 默认输出（wpctl，兼容 HDMI/模拟输出）。"""
        if self.config.mock:
            logger.info(tr("volume_mock").format(action))
            return
        try:
            delta = "0.05+" if action == "volume_up" else "0.05-"
            subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_SINK@", delta])
        except Exception as e:
            logger.error("音量调整失败: %s", e)

    def _power_menu(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(tr("power_menu_title"))
        box.setText(tr("power_choice"))
        reboot = box.addButton(tr("reboot"), QMessageBox.AcceptRole)
        shutdown = box.addButton(tr("shutdown"), QMessageBox.AcceptRole)
        box.addButton(tr("cancel"), QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked == reboot:
            self._sys_command(["sudo", "reboot"], "reboot")
        elif clicked == shutdown:
            self._sys_command(["sudo", "shutdown", "-h", "now"], "shutdown")

    def exit_box(self) -> None:
        """退出电视盒子。
        kiosk 模式（cage 会话）：终止会话回 GDM 登录界面（要密码，天然安全）。
        桌面模式（GNOME 会话）：默认锁屏（exit_nopasswd=False），可设免密直退。"""
        box = QMessageBox(self)
        box.setWindowTitle(tr("power_exit"))
        box.setText(tr("exit_confirm"))
        ok = box.addButton(tr("exit_confirm_ok"), QMessageBox.AcceptRole)
        box.addButton(tr("cancel"), QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() == ok:
            logger.info("退出电视盒子")
            if self._is_kiosk():
                self._terminate_session()
            elif not self.config.get("exit_nopasswd", False):
                self._lock_screen()
            self.remote.stop()
            QApplication.instance().quit()

    def _start_vnc(self) -> None:
        """kiosk 模式（labwc）下启动 wayvnc，供局域网 VNC 远程查看/操作。
        密码空则无密码（局域网信任环境）；有密码用 --password。"""
        if self.config.mock or not self._is_kiosk():
            return
        if not shutil.which("wayvnc"):
            logger.info("wayvnc 未安装，跳过 VNC")
            return
        try:
            pw = str(self.config.get("vnc_password", "") or "")
            cmd = ["wayvnc", "0.0.0.0"]
            if pw:
                cmd += ["--password", pw]
            subprocess.Popen(cmd)
            logger.info("VNC 已启动 (wayvnc%s)", " 带密码" if pw else " 无密码")
        except Exception as e:
            logger.error("wayvnc 启动失败: %s", e)

    def _is_kiosk(self) -> bool:
        """是否运行在 kiosk 模式（TVIEW 专用 labwc 会话，L2）。
        检测：GDM 会话名 tview（XDG_SESSION_DESKTOP / GDMSESSION）。"""
        import os
        desk = os.environ.get("XDG_SESSION_DESKTOP", "") or os.environ.get("GDMSESSION", "")
        return desk.lower() == "tview"

    def _terminate_session(self) -> None:
        """终止当前会话（回 GDM 登录界面）。kiosk 模式退出盒子用。"""
        if self.config.mock:
            logger.info("终止会话 - mock")
            return
        try:
            subprocess.Popen(["loginctl", "terminate-session"])
            logger.info("已终止会话（回登录界面）")
        except Exception as e:
            logger.error("终止会话失败: %s", e)

    def _lock_screen(self) -> None:
        """锁屏（GNOME 会话锁，解锁需密码）。退出盒子默认动作，防免密桌面被他人利用。"""
        if self.config.mock:
            logger.info("锁屏 - mock")
            return
        try:
            subprocess.Popen(["loginctl", "lock-session"])
            logger.info("已触发锁屏")
        except Exception as e:
            logger.error("锁屏失败: %s", e)

    def _sys_command(self, cmd: list[str], label: str) -> None:
        if self.config.mock:
            logger.info("系统命令(%s): %s - mock", label, " ".join(cmd))
            return
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            logger.error("%s失败: %s", label, e)

    # ---------------- 看门狗 ----------------
    def _watchdog(self) -> None:
        """waydroid 存活检测：3 次失败重启会话，3 次重启失败回主界面提示。"""
        if self.config.mock:
            return
        ok = self.waydroid.session_running()
        if ok:
            self._wd_fails = 0
            self._wd_restarts = 0
            return
        self._wd_fails += 1
        if self._wd_fails < 3:
            logger.warning("Waydroid 无响应 %d/3", self._wd_fails)
            return
        self._wd_fails = 0
        self._wd_restarts += 1
        if self._wd_restarts > 3:
            logger.error("Waydroid 重启 3 次失败，回主界面")
            self._toast(tr("toast_wd_fail"))
            self.show_home()
            return
        logger.warning("重启 Waydroid 会话 (%d/3)", self._wd_restarts)
        # session stop/start 可能耗时数十秒，放后台线程，避免冻结 UI
        threading.Thread(target=self._wd_restart_session, daemon=True,
                         name="wd-restart").start()

    def _wd_restart_session(self) -> None:
        """后台重启会话（先停后启，间隔 2s）。"""
        try:
            self.waydroid.session_stop()
        except Exception as e:
            logger.error("停止 Waydroid 会话失败: %s", e)
        time.sleep(2)
        try:
            self.waydroid.session_start()
        except Exception as e:
            logger.error("启动 Waydroid 会话失败: %s", e)

    # ---------------- 工具 ----------------
    def _toast(self, msg: str) -> None:
        self.toast.setText(msg)
        self.toast.adjustSize()
        self.toast.move((self.width() - self.toast.width()) // 2,
                        self.height() - 120)
        self.toast.show()
        QTimer.singleShot(2500, self.toast.hide)

    def closeEvent(self, event):
        self.remote.stop()
        self._dock_restore()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)

    # ---------------- Dock 自动隐藏（测试期 GNOME 环境） ----------------
    def _dock_hide(self) -> None:
        """启动时把 Ubuntu Dock 切成自动隐藏（保存原值，退出恢复）。"""
        if self.config.mock:
            return
        try:
            r = subprocess.run(["gsettings", "get", "org.gnome.shell.extensions.dash-to-dock", "dock-fixed"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return  # 无 dash-to-dock（非 GNOME/扩展未装）
            self._dock_orig = r.stdout.strip()
            subprocess.run(["gsettings", "set", "org.gnome.shell.extensions.dash-to-dock", "dock-fixed", "false"],
                           timeout=5)
            subprocess.run(["gsettings", "set", "org.gnome.shell.extensions.dash-to-dock", "autohide", "true"],
                           timeout=5)
            logger.info("Dock 已切换为自动隐藏")
        except Exception as e:
            logger.warning("Dock 隐藏失败: %s", e)

    def _dock_restore(self) -> None:
        """退出时恢复 Dock 原状。"""
        if self.config.mock or not getattr(self, "_dock_orig", None):
            return
        try:
            subprocess.run(["gsettings", "set", "org.gnome.shell.extensions.dash-to-dock",
                            "dock-fixed", self._dock_orig], timeout=5)
            logger.info("Dock 已恢复")
        except Exception as e:
            logger.warning("Dock 恢复失败: %s", e)


class SettingsDialog(QDialog):
    """设置弹窗：列数/壁纸/语言/自启/免密登录/Waydroid 控制/映射/添加应用/退出盒子等。

    样式统一走 QApplication 全局样式表（BASE_STYLE），不在本类重复 setStyleSheet，
    避免子控件缺 color 导致“黑字蓝底”看不清。
    """

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.changed = False
        self.setWindowTitle(tr("dlg_settings"))

        root = QVBoxLayout(self)

        # 列数（拖动实时生效）
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("columns")))
        self.cols_slider = QSlider(Qt.Horizontal)
        self.cols_slider.setRange(2, 6)
        self.cols_slider.setValue(int(config.get("columns", 3)))
        self.cols_label = QLabel(str(self.cols_slider.value()))
        self.cols_slider.valueChanged.connect(self._live_apply)
        row.addWidget(self.cols_slider)
        row.addWidget(self.cols_label)
        root.addLayout(row)

        # 壁纸
        row2 = QHBoxLayout()
        btn_wall = QPushButton(tr("wallpaper"))
        btn_wall.clicked.connect(self._pick_wallpaper)
        self.wall_label = QLabel(config.get("wallpaper") or tr("wallpaper_none"))
        row2.addWidget(btn_wall)
        row2.addWidget(self.wall_label, 1)
        root.addLayout(row2)

        # 语言（重启生效）
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Language / 语言:"))
        self.lang_box = QComboBox()
        self.lang_box.addItem("中文", "zh")
        self.lang_box.addItem("English", "en")
        cur = config.get("language", "zh")
        self.lang_box.setCurrentIndex(0 if cur != "en" else 1)
        self.lang_box.currentIndexChanged.connect(self._change_lang)
        row3.addWidget(self.lang_box, 1)
        root.addLayout(row3)

        # 主题（即时生效）
        row4 = QHBoxLayout()
        row4.addWidget(QLabel(tr("theme")))
        self.theme_box = QComboBox()
        for key, t in THEMES.items():
            self.theme_box.addItem(f"{t['name_zh']} · {t['name']}", key)
        self.theme_box.addItem(tr("theme_custom"), "custom")
        cur = config.get("theme", "minimal")
        idx = self.theme_box.findData(cur)
        self.theme_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.theme_box.currentIndexChanged.connect(self._change_theme)
        row4.addWidget(self.theme_box, 1)
        btn_custom = QPushButton(tr("theme_custom"))
        btn_custom.clicked.connect(self._edit_theme)
        row4.addWidget(btn_custom)
        root.addLayout(row4)

        # Waydroid 状态显示开关（默认开）
        self.wd_show = QCheckBox(tr("wd_status_show"))
        self.wd_show.setChecked(bool(config.get("wd_status_show", True)))
        self.wd_show.toggled.connect(
            lambda v: (config.set("wd_status_show", v), setattr(self, "changed", True)))
        root.addWidget(self.wd_show)

        # 开机自启（设置里可开关）
        self.autostart_chk = QCheckBox(tr("autostart"))
        self.autostart_chk.setChecked(bool(config.get("autostart", True)))
        self.autostart_chk.toggled.connect(self._toggle_autostart)
        root.addWidget(self.autostart_chk)

        # 开机免密直接进 TVIEW（GDM autologin）
        self.autologin_chk = QCheckBox(tr("autologin"))
        st = self.parent()._autologin_status() if self.parent() else None
        if st is None:
            self.autologin_chk.setChecked(False)
            self.autologin_chk.setEnabled(False)
            self.autologin_chk.setToolTip(tr("autologin_no_perm"))
        else:
            self.autologin_chk.setChecked(st)
            self.autologin_chk.toggled.connect(self._toggle_autologin)
        root.addWidget(self.autologin_chk)

        # 运行模式（L1/L2 整合：盒子模式 / 桌面模式 / 正常登录）
        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel(tr("mode")))
        self.mode_box = QComboBox()
        self.mode_box.addItem(tr("mode_kiosk"), "tview")
        self.mode_box.addItem(tr("mode_desktop"), "gnome")
        self.mode_box.addItem(tr("mode_normal"), "off")
        st = self.parent()._autologin_status() if self.parent() else None
        if st is None:
            self.mode_box.setEnabled(False)
            self.mode_box.setToolTip(tr("autologin_no_perm"))
        else:
            session = self.parent()._autologin_session() if self.parent() else "gnome"
            cur = "tview" if session == "tview" else ("gnome" if st else "off")
            idx = self.mode_box.findData(cur)
            self.mode_box.setCurrentIndex(idx if idx >= 0 else 0)
            self.mode_box.currentIndexChanged.connect(self._change_mode)
        row_mode.addWidget(self.mode_box, 1)
        root.addLayout(row_mode)
        hint_mode = QLabel(tr("mode_hint"))
        hint_mode.setWordWrap(True)
        root.addWidget(hint_mode)

        # 显示器唤醒 TVIEW（BETA 0.3：桌面模式下检测显示器开启 → 自动进入 TVIEW）
        self.dw_chk = QCheckBox(tr("dw_enabled"))
        _dw = config.get("display_wake") or {}
        self.dw_chk.setChecked(bool(_dw.get("enabled", True)))
        self.dw_chk.toggled.connect(self._toggle_dw)
        root.addWidget(self.dw_chk)

        self.dw_any = QRadioButton(tr("dw_mode_any"))
        self.dw_specific = QRadioButton(tr("dw_mode_specific"))
        self.dw_any.setChecked(_dw.get("mode", "any") == "any")
        self.dw_specific.setChecked(_dw.get("mode", "any") != "any")
        self.dw_any.toggled.connect(lambda v: self._set_dw_mode("any" if v else "specific"))
        root.addWidget(self.dw_any)
        root.addWidget(self.dw_specific)

        self.dw_list = QListWidget()
        self.dw_list.setMinimumHeight(110)
        self.dw_list.itemChanged.connect(self._save_dw_targets)
        root.addWidget(self.dw_list)
        btn_dw_refresh = QPushButton(tr("dw_refresh"))
        btn_dw_refresh.clicked.connect(self._refresh_dw_list)
        root.addWidget(btn_dw_refresh)
        hint_dw = QLabel(tr("dw_hint"))
        hint_dw.setWordWrap(True)
        root.addWidget(hint_dw)
        self._refresh_dw_list()
        self._sync_dw_enabled()

        # 退出盒子后是否免密进桌面（默认关=退出时锁屏，更安全）
        self.exit_nopasswd_chk = QCheckBox(tr("exit_nopasswd"))
        self.exit_nopasswd_chk.setChecked(bool(config.get("exit_nopasswd", False)))
        self.exit_nopasswd_chk.toggled.connect(self._toggle_exit_nopasswd)
        root.addWidget(self.exit_nopasswd_chk)
        hint = QLabel(tr("exit_nopasswd_hint"))
        hint.setWordWrap(True)
        root.addWidget(hint)

        # 自定义遥控器映射入口
        btn_keymap = QPushButton(tr("keymap_btn"))
        btn_keymap.clicked.connect(self._open_keymap)
        root.addWidget(btn_keymap)

        # Waydroid 控制
        wd_row = QHBoxLayout()
        for text, slot in [(tr("wd_start"), self._wd_start),
                           (tr("wd_stop"), self._wd_stop),
                           (tr("wd_restart"), self._wd_restart)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            wd_row.addWidget(b)
        root.addLayout(wd_row)

        # 添加应用
        btn_add = QPushButton(tr("add_linux_app"))
        btn_add.clicked.connect(self._add_app)
        root.addWidget(btn_add)

        # U盘安装入口
        btn_usb = QPushButton(tr("usb_install_btn"))
        btn_usb.clicked.connect(self._usb_install)
        root.addWidget(btn_usb)

        # 操作按钮（重启/关机已收进主界面电源菜单，这里只留日志导出）
        for text, slot in [
            (tr("export_logs"), self._export_logs),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            root.addWidget(b)

        # 关于
        btn_about = QPushButton(tr("about"))
        btn_about.clicked.connect(self._show_about)
        root.addWidget(btn_about)

        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        root.addWidget(close)

    def _show_about(self) -> None:
        """关于弹窗：版本号 + 项目信息。"""
        from .. import __version__
        QMessageBox.about(
            self,
            tr("app_title"),
            f"{tr('app_title')} {__version__}\n\n"
            f"{tr('about_line1')}\n{tr('about_line2')}\n\n"
            f"{tr('about_line3')}",
        )

    def _live_apply(self) -> None:
        """列数实时生效：立即保存并重排主界面网格。"""
        v = self.cols_slider.value()
        self.cols_label.setText(str(v))
        self.config.set("columns", v)
        self.changed = True
        parent = self.parent()
        if parent is not None and hasattr(parent, "render_grid"):
            parent.render_grid()

    def _change_theme(self, idx: int) -> None:
        """切换内置主题：立即生效（重新生成全局 QSS + 壁纸）。"""
        key = self.theme_box.itemData(idx)
        if not key:
            return
        self.config.set("theme", key)
        self.changed = True
        parent = self.parent()
        if parent is not None:
            parent.apply_theme()

    def _edit_theme(self) -> None:
        """自定义主题编辑。"""
        parent = self.parent()
        if parent is None:
            return
        dlg = ThemeEditDialog(parent.config, parent, self)
        if dlg.exec_():
            parent.apply_theme()
            idx = self.theme_box.findData("custom")
            if idx >= 0:
                self.theme_box.setCurrentIndex(idx)

    def _toggle_autostart(self, v: bool) -> None:
        """开机自启开关：写/删 autostart desktop 文件。"""
        self.config.set("autostart", v)
        self.changed = True
        parent = self.parent()
        if parent is not None:
            parent._apply_autostart(v)

    def _toggle_exit_nopasswd(self, v: bool) -> None:
        """退出盒子免密开关：关（默认）=退出即锁屏，开=直接回桌面。"""
        self.config.set("exit_nopasswd", v)
        self.changed = True

    def _change_lang(self, idx: int) -> None:
        """语言切换：保存配置，提示重启生效（当前界面保持原语言直到重启）。"""
        lang = self.lang_box.itemData(idx)
        self.config.set("language", lang)
        self.config.save()
        self.changed = True
        QMessageBox.information(self, tr("dlg_settings"), tr("lang_restart"))

    def _toggle_autologin(self, v: bool) -> None:
        """开机免密开关：调用系统脚本改 GDM 配置，重启后生效。"""
        parent = self.parent()
        if parent is None:
            return
        ok, err = parent._apply_autologin(v)
        if ok:
            self.changed = True
            QMessageBox.information(self, tr("dlg_settings"), tr("autologin_restart"))
        else:
            QMessageBox.warning(self, tr("dlg_settings"), err or tr("autologin_fail"))

    def _change_mode(self, idx: int) -> None:
        """运行模式切换（L1/L2 整合）：盒子模式/桌面模式/正常登录，调 autologin 脚本。"""
        parent = self.parent()
        if parent is None:
            return
        mode = self.mode_box.itemData(idx)
        ok, err = parent._apply_mode(mode)
        if ok:
            self.changed = True
            QMessageBox.information(self, tr("dlg_settings"), tr("mode_restart"))
        else:
            QMessageBox.warning(self, tr("dlg_settings"), err or tr("autologin_fail"))

    # ---------------- 显示器唤醒 TVIEW（BETA 0.3） ----------------
    def _dw_config(self) -> dict:
        dw = dict(self.config.get("display_wake") or {})
        dw.setdefault("enabled", True)
        dw.setdefault("mode", "any")
        dw.setdefault("targets", [])
        return dw

    def _save_dw(self, dw: dict) -> None:
        self.config.set("display_wake", dw)
        self.config.save()
        self.changed = True

    def _toggle_dw(self, v: bool) -> None:
        dw = self._dw_config()
        dw["enabled"] = v
        self._save_dw(dw)
        self._sync_dw_enabled()

    def _set_dw_mode(self, mode: str) -> None:
        dw = self._dw_config()
        dw["mode"] = mode
        self._save_dw(dw)
        self._sync_dw_enabled()

    def _sync_dw_enabled(self) -> None:
        """开关关闭时禁用子选项。"""
        en = self.dw_chk.isChecked()
        self.dw_any.setEnabled(en)
        self.dw_specific.setEnabled(en)
        self.dw_list.setEnabled(en and self.dw_specific.isChecked())

    def _refresh_dw_list(self) -> None:
        """扫描当前开启的显示器（EDID 可读），勾选状态对应当前配置。"""
        self.dw_list.blockSignals(True)
        self.dw_list.clear()
        targets = set((self._dw_config()).get("targets") or [])
        ons = [c for c in list_connectors() if c["on"]]
        if not ons:
            item = QListWidgetItem(tr("dw_none_found"))
            item.setFlags(Qt.NoItemFlags)
            self.dw_list.addItem(item)
        else:
            for c in ons:
                item = QListWidgetItem(disp_label(c))
                item.setData(Qt.UserRole, c["connector"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if c["connector"] in targets else Qt.Unchecked)
                self.dw_list.addItem(item)
        self.dw_list.blockSignals(False)

    def _save_dw_targets(self, item) -> None:
        """勾选变化 → 保存 targets。"""
        if not item.data(Qt.UserRole):
            return
        dw = self._dw_config()
        checked = []
        for i in range(self.dw_list.count()):
            it = self.dw_list.item(i)
            conn = it.data(Qt.UserRole)
            if conn and it.checkState() == Qt.Checked:
                checked.append(conn)
        dw["targets"] = checked
        self._save_dw(dw)

    def _open_keymap(self) -> None:
        """打开遥控器按键映射对话框。"""
        parent = self.parent()
        if parent is None:
            return
        dlg = KeyMapDialog(parent.config, parent)
        dlg.exec_()

    def _wd_start(self) -> None:
        w = self.parent()
        if w is None or w.config.mock:
            return
        ok = w.waydroid.session_start()
        QMessageBox.information(self, tr("dlg_settings"), tr("wd_cmd_ok") if ok else tr("wd_cmd_fail"))

    def _wd_stop(self) -> None:
        w = self.parent()
        if w is None or w.config.mock:
            return
        w.waydroid.session_stop()
        QMessageBox.information(self, tr("dlg_settings"), tr("wd_stop_ok"))

    def _wd_restart(self) -> None:
        w = self.parent()
        if w is None or w.config.mock:
            return
        w.waydroid.session_stop()
        w.waydroid.session_start()
        QMessageBox.information(self, tr("dlg_settings"), tr("wd_restart_ok"))

    def _add_app(self) -> None:
        """添加自定义 Linux 应用（名称/命令/图标）。"""
        w = self.parent()
        if w is None:
            return
        dlg = AddAppDialog(w.app_mgr, self)
        if dlg.exec_() and dlg.result_name:
            w.refresh_apps()
            self.changed = True

    def _usb_install(self) -> None:
        w = self.parent()
        if w is not None:
            self.accept()
            w.open_usb_install()

    def keyPressEvent(self, e):
        """遥控器方向键导航（修复滑块卡死）+ 返回/回车退出。"""
        k = e.key()
        if k in (Qt.Key_Up, Qt.Key_Down) and isinstance(self.focusWidget(), QSlider):
            # 滑块上：上/下键离开滑块（左右键留给滑块调值）
            if k == Qt.Key_Down:
                self.focusNextChild()
            else:
                self.focusPreviousChild()
            return
        if k in (Qt.Key_Backspace, Qt.Key_Escape):
            self.reject()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            w = self.focusWidget()
            if isinstance(w, QPushButton):
                w.click()
            return
        super().keyPressEvent(e)

    def _pick_wallpaper(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("wallpaper"), "", "图片 (*.png *.jpg *.jpeg)")
        if path:
            self.config.set("wallpaper", path)
            self.changed = True
            self.wall_label.setText(path)

    def _sys(self, cmd: str) -> None:
        if self.config.mock:
            logger.info("系统命令: %s - mock", cmd)
            return
        subprocess.Popen(cmd.split())

    def _export_logs(self) -> None:
        import tarfile
        out = Path.home() / f"tview-logs-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            for f in LOG_DIR.glob("*.log"):
                tar.add(f, arcname=f.name)
        QMessageBox.information(self, tr("export_logs"), tr("logs_exported").format(out))

    def accept(self) -> None:
        # 保存列数等
        self.config.set("columns", self.cols_slider.value())
        super().accept()


class ThemeEditDialog(QDialog):
    """自定义主题编辑：颜色项 + 壁纸，保存时自动对比度修正（WCAG）。"""

    KEYS = ["bg1", "bg2", "card", "card_border", "focus", "text", "text_dim", "accent"]

    def __init__(self, config, main_win, parent=None):
        super().__init__(parent)
        self.config = config
        self.win = main_win
        self.values = dict(config.get("custom_theme") or {})
        self.setWindowTitle(tr("theme_custom"))
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        labels = tr("theme_items") or {}
        self._rows: dict[str, QPushButton] = {}
        for k in self.KEYS:
            row = QHBoxLayout()
            row.addWidget(QLabel(labels.get(k, k)))
            btn = QPushButton()
            btn.setFixedSize(130, 34)
            btn.clicked.connect(lambda _, kk=k: self._pick(kk))
            row.addWidget(btn)
            row.addStretch(1)
            root.addLayout(row)
            self._rows[k] = btn

        wrow = QHBoxLayout()
        wrow.addWidget(QLabel(tr("theme_wallpaper")))
        self.wall_btn = QPushButton(tr("theme_choose_wallpaper"))
        self.wall_btn.clicked.connect(self._pick_wallpaper)
        self.wall_clear = QPushButton(tr("theme_clear_wallpaper"))
        self.wall_clear.clicked.connect(self._clear_wallpaper)
        wrow.addWidget(self.wall_btn)
        wrow.addWidget(self.wall_clear)
        root.addLayout(wrow)
        self.wall_label = QLabel()
        root.addWidget(self.wall_label)

        btns = QHBoxLayout()
        reset = QPushButton(tr("theme_reset"))
        reset.clicked.connect(self._reset)
        ok = QPushButton(tr("app_ok"))
        ok.clicked.connect(self._save)
        cancel = QPushButton(tr("app_cancel"))
        cancel.clicked.connect(self.reject)
        btns.addWidget(reset)
        btns.addStretch(1)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        root.addLayout(btns)
        self._refresh()

    def _refresh(self) -> None:
        for k, btn in self._rows.items():
            v = self.values.get(k) or "#888888"
            btn.setText(v)
            btn.setStyleSheet(
                f"background:{v};border:1px solid #666;border-radius:6px;color:#ffffff;")
        wp = self.values.get("wallpaper_path")
        self.wall_label.setText(wp if wp else tr("theme_wallpaper_auto"))

    def _pick(self, k: str) -> None:
        from PyQt5.QtGui import QColorDialog
        cur = QColor(self.values.get(k) or "#ffffff")
        c = QColorDialog.getColor(cur, self, tr("theme"))
        if c.isValid():
            self.values[k] = c.name()
            self._refresh()

    def _pick_wallpaper(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("theme_choose_wallpaper"), "",
                                              "图片 (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.values["wallpaper_path"] = path
            self._refresh()

    def _clear_wallpaper(self) -> None:
        self.values.pop("wallpaper_path", None)
        self._refresh()

    def _reset(self) -> None:
        self.values = {}
        self._refresh()

    def _save(self) -> None:
        """保存并应用自定义主题；文字色与背景对比度不足时自动修正。"""
        bg1 = self.values.get("bg1", "#10162a")
        fixed: list[str] = []
        for k in ("text", "text_dim"):
            if k in self.values:
                new = ensure_contrast(self.values[k], bg1)
                if new != self.values[k]:
                    self.values[k] = new
                    fixed.append(k)
        self.config.set("custom_theme", self.values)
        self.config.set("theme", "custom")
        self.config.save()
        self.accept()
        if fixed:
            QMessageBox.information(self.win, tr("theme"),
                                    tr("theme_contrast_fix"))

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Backspace, Qt.Key_Escape):
            self.reject()
            return
        super().keyPressEvent(e)


class KeyMapDialog(QDialog):
    """自定义遥控器按键映射：选按键 → 录制 → 指派动作 → 保存。

    基于 keyd 标准化后的 Qt 键（或遥控器合成事件），映射存 config.remote_keymap
    {Qt键值(int): 动作(str)}，优先级高于系统默认；恢复默认=清空映射。
    """

    # 可映射的标准键（keyd 标准化后的 Qt 键）与友好名（多语言）
    KEYS = [
        (Qt.Key_Up, tr("key_up")), (Qt.Key_Down, tr("key_down")),
        (Qt.Key_Left, tr("key_left")), (Qt.Key_Right, tr("key_right")),
        (Qt.Key_Return, tr("key_ok")), (Qt.Key_Back, tr("key_back")),
        (Qt.Key_Backspace, tr("key_settings")), (Qt.Key_Home, tr("key_home")),
        (Qt.Key_Menu, tr("key_menu")), (Qt.Key_VolumeUp, tr("key_volup")),
        (Qt.Key_VolumeDown, tr("key_voldown")),
    ]
    # 可选动作：action 字符串与代码一致（多语言）
    ACTIONS = [
        ("up", tr("act_up")), ("down", tr("act_down")),
        ("left", tr("act_left")), ("right", tr("act_right")),
        ("enter", tr("act_enter")), ("back", tr("act_back")),
        ("home", tr("act_home")), ("menu", tr("act_menu")),
        ("settings", tr("act_settings")), ("market", tr("act_market")),
        ("volume_up", tr("act_volup")), ("volume_down", tr("act_voldown")),
        ("power", tr("act_power")), ("ignore", tr("act_ignore")),
    ]

    def __init__(self, config, main_win, parent=None):
        super().__init__(parent)
        self.config = config
        self.win = main_win
        self.km = dict(config.get("remote_keymap") or {})
        self.setWindowTitle(tr("dlg_keymap"))
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(tr("keymap_hint")))
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(lambda _: self._refresh_action_box())
        root.addWidget(self.list_widget, 1)

        row = QHBoxLayout()
        self.btn_remap = QPushButton(tr("keymap_remap"))
        self.btn_remap.clicked.connect(self._start_record)
        self.btn_reset = QPushButton(tr("keymap_reset"))
        self.btn_reset.clicked.connect(self._reset_all)
        row.addWidget(self.btn_remap)
        row.addWidget(self.btn_reset)
        root.addLayout(row)

        self.record_label = QLabel("")
        self.record_label.setStyleSheet("font-size:15px;color:#f0a35e;min-height:22px;")
        root.addWidget(self.record_label)

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel(tr("keymap_action")))
        self.action_box = QComboBox()
        for a, label in self.ACTIONS:
            self.action_box.addItem(label, a)
        self.btn_save = QPushButton(tr("keymap_save"))
        self.btn_save.clicked.connect(self._save_current)
        action_row.addWidget(self.action_box, 1)
        action_row.addWidget(self.btn_save)
        root.addLayout(action_row)

        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        root.addWidget(close)
        self._reload_list()

    # ---- 列表与动作 ----
    def _default_action(self, qt_key: int) -> str | None:
        """系统默认动作（与 eventFilter/on_remote_key 语义一致）。"""
        m = {Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right",
             Qt.Key_Return: "enter", Qt.Key_Back: "back", Qt.Key_Backspace: "settings",
             Qt.Key_Home: "home", Qt.Key_Menu: "menu",
             Qt.Key_VolumeUp: "volume_up", Qt.Key_VolumeDown: "volume_down"}
        return m.get(qt_key)

    def _action_label(self, action: str) -> str:
        for a, label in self.ACTIONS:
            if a == action:
                return label
        return action or "—"

    def _reload_list(self) -> None:
        self.list_widget.clear()
        for qt_key, name in self.KEYS:
            act = self.km.get(str(qt_key))
            if act:
                text = f"{name}  →  {self._action_label(act)}  {tr('keymap_custom')}"
            else:
                d = self._default_action(qt_key)
                text = f"{name}  →  {self._action_label(d)}  {tr('keymap_default')}" if d else f"{name}  {tr('keymap_unmapped')}"
            self.list_widget.addItem(text)
        self.list_widget.setCurrentRow(0)

    def _refresh_action_box(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        qt_key = self.KEYS[row][0]
        act = self.km.get(str(qt_key))
        idx = 0
        for i, (a, _) in enumerate(self.ACTIONS):
            if a == act:
                idx = i
                break
        self.action_box.setCurrentIndex(idx)

    # ---- 录制 ----
    def _start_record(self) -> None:
        if self.list_widget.currentRow() < 0:
            return
        self.record_label.setText(tr("keymap_record"))
        self.win._recording_cb = self._on_captured
        QTimer.singleShot(10000, self._record_timeout)

    def _record_timeout(self) -> None:
        if getattr(self.win, "_recording_cb", None) is self._on_captured:
            self.win._recording_cb = None
            self.record_label.setText(tr("keymap_timeout"))

    def _on_captured(self, qt_key: int) -> None:
        name = self._key_name(qt_key)
        self.record_label.setText(tr("keymap_captured").format(name))
        for i, (k, _) in enumerate(self.KEYS):
            if k == qt_key:
                self.list_widget.setCurrentRow(i)
                break

    def _key_name(self, qt_key: int) -> str:
        for k, n in self.KEYS:
            if k == qt_key:
                return n
        return tr("key_code").format(qt_key)

    # ---- 保存/重置 ----
    def _save_current(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        qt_key = self.KEYS[row][0]
        action = self.action_box.currentData()
        if action in (None, "ignore"):
            self.km.pop(str(qt_key), None)
        else:
            self.km[str(qt_key)] = action
        self.config.set("remote_keymap", self.km)
        self.config.save()
        self._reload_list()
        self.record_label.setText(tr("keymap_saved"))

    def _reset_all(self) -> None:
        self.km = {}
        self.config.set("remote_keymap", {})
        self.config.save()
        self._reload_list()
        self.record_label.setText(tr("keymap_reset_done"))

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Backspace, Qt.Key_Escape):
            self.accept()
            return
        super().keyPressEvent(e)


class AddAppDialog(QDialog):
    """添加 Linux 应用：名称 + 启动命令 + 图标选择器。"""

    def __init__(self, app_mgr, parent=None):
        super().__init__(parent)
        self.app_mgr = app_mgr
        self.result_name = ""
        self.icon_path = ""
        self.setWindowTitle(tr("dlg_add_app"))
        root = QVBoxLayout(self)
        root.addWidget(QLabel(tr("app_name")))
        self.name_edit = QLineEdit()
        root.addWidget(self.name_edit)
        root.addWidget(QLabel(tr("app_cmd")))
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText(tr("app_cmd_hint"))
        root.addWidget(self.cmd_edit)

        icon_row = QHBoxLayout()
        self.icon_preview = QLabel(tr("app_no_icon"))
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setStyleSheet("border:1px solid #3a4a6b;border-radius:6px;")
        btn_icon = QPushButton(tr("app_icon"))
        btn_icon.clicked.connect(self._pick_icon)
        icon_row.addWidget(self.icon_preview)
        icon_row.addWidget(btn_icon)
        root.addLayout(icon_row)

        ok_row = QHBoxLayout()
        btn_ok = QPushButton(tr("app_ok"))
        btn_ok.clicked.connect(self._ok)
        btn_cancel = QPushButton(tr("app_cancel"))
        btn_cancel.clicked.connect(self.reject)
        ok_row.addWidget(btn_ok)
        ok_row.addWidget(btn_cancel)
        root.addLayout(ok_row)
        self.name_edit.setFocus()

    def _pick_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("icon_choose"), "", "图片 (*.png *.jpg *.jpeg *.svg)")
        if path:
            self.icon_path = path
            self.icon_preview.setPixmap(QPixmap(path).scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _ok(self) -> None:
        name = self.name_edit.text().strip()
        cmd = self.cmd_edit.text().strip()
        if not name or not cmd:
            QMessageBox.warning(self, tr("dlg_add_app"), tr("app_empty"))
            return
        self.result_name = name
        self.app_mgr.add_linux_app(name, cmd, self.icon_path)
        self.accept()

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Return, Qt.Key_Enter):
            w = self.focusWidget()
            if isinstance(w, QPushButton):
                w.click()
            return
        if k in (Qt.Key_Backspace, Qt.Key_Escape):
            self.reject()
            return
        super().keyPressEvent(e)


class UsbInstallDialog(QDialog):
    """U盘 APK 安装（遥控器全流程）：列出 APK → 选择 → 安装 → 结果。"""

    def __init__(self, waydroid, config, parent=None):
        super().__init__(parent)
        self.waydroid = waydroid
        self.config = config
        self.setWindowTitle(tr("dlg_usb_install"))
        root = QVBoxLayout(self)
        root.addWidget(QLabel(tr("usb_list")))
        self.list_widget = QVBoxLayout()
        root.addLayout(self.list_widget)
        btn_refresh = QPushButton(tr("usb_refresh"))
        btn_refresh.clicked.connect(self._reload)
        root.addWidget(btn_refresh)
        btn_close = QPushButton(tr("close"))
        btn_close.clicked.connect(self.accept)
        root.addWidget(btn_close)
        self._reload()

    def _reload(self) -> None:
        """列出 U 盘 APK。"""
        while self.list_widget.count():
            item = self.list_widget.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        apks = self.parent()._usb_apk_paths() if self.parent() else []
        if not apks:
            self.list_widget.addWidget(QLabel(tr("usb_none")))
            return
        for apk in sorted(apks, key=lambda p: p.name):
            btn = QPushButton(f"📦 {apk.name}  ({apk.parent.name}/)")
            btn.clicked.connect(lambda _, p=apk: self._install(p))
            self.list_widget.addWidget(btn)

    def _install(self, apk: Path) -> None:
        """安装选中的 APK。"""
        progress = QProgressDialog(tr("usb_installing").format(apk.name), None, 0, 0, self)
        progress.setWindowTitle(tr("usb_install_title"))
        progress.show()
        QApplication.processEvents()
        try:
            ok = self.waydroid.app_install(str(apk))
        finally:
            progress.close()
        if ok:
            QMessageBox.information(self, tr("usb_install_ok"), tr("usb_install_ok_msg").format(apk.name))
        else:
            QMessageBox.warning(self, tr("usb_install_fail"), tr("usb_install_fail_msg").format(apk.name))

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Return, Qt.Key_Enter):
            w = self.focusWidget()
            if isinstance(w, QPushButton):
                w.click()
            return
        if k in (Qt.Key_Backspace, Qt.Key_Escape):
            self.reject()
            return
        super().keyPressEvent(e)


class _MarketWorker(QObject):
    """后台下载：依次尝试多个 URL（HEAD 探测 → 分块下载，可取消，读写超时 60s）。

    必须在后台线程执行：f-droid.org 等源在国内常不可达/限速，
    若在主线程同步下载（无超时的 urlretrieve）会永久冻结 UI。
    """
    finished = pyqtSignal(bool, str, str)  # (ok, apk_path, error)

    def __init__(self, pkg: str, urls: list[str], parent=None):
        super().__init__(parent)
        self.pkg = pkg
        self.urls = urls
        self._cancel = False
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="market-download")

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        self._cancel = True

    def _run(self) -> None:
        import urllib.request
        tmp = Path("/tmp") / f"tview-{self.pkg}.apk"
        dst = tmp.with_suffix(".part")
        last_err = ""
        for url in self.urls:
            try:
                # HEAD 探测（10s 超时，含连接）
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as r:
                    if r.status != 200:
                        raise RuntimeError(f"HTTP {r.status}")
                # 分块下载：urlopen timeout 对每次 socket 读写生效，堵死 60s 内必报错
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
                    while True:
                        if self._cancel:
                            self.finished.emit(False, "", tr("market_cancel"))
                            return
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                dst.replace(tmp)
                self.finished.emit(True, str(tmp), "")
                return
            except Exception as e:
                last_err = str(e)
                logger.warning("下载源失败 %s: %s", url, e)
                try:
                    dst.unlink(missing_ok=True)
                except Exception:
                    pass
        self.finished.emit(False, "", last_err)


class _InstallWorker(QObject):
    """后台执行 waydroid app install（避免安装过程冻结 UI 数十秒）。"""
    finished = pyqtSignal(bool, str)  # (ok, error)

    def __init__(self, waydroid, apk_path: str, parent=None):
        super().__init__(parent)
        self.waydroid = waydroid
        self.apk_path = apk_path
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="market-install")

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            ok = self.waydroid.app_install(self.apk_path)
            self.finished.emit(bool(ok), "" if ok else tr("install_fail_waydroid"))
        except Exception as e:
            self.finished.emit(False, str(e))


class MarketDialog(QDialog):
    """应用下载：当贝市场（内置资产）+ F-Droid（内置资产/国内源，多 URL 回退）。"""

    ITEMS = [
        (tr("market_dangbei"), "com.dangbeimarket",
         "assets/apks/dangbeimarket.apk",
         ["http://znds.tvapk.com/update/dbmarket.apk"]),
        # F-Droid：内置资产优先，其次 GitHub 直链（国内可达），最后官方源
        (tr("market_fdroid"), "org.fdroid.fdroid",
         "assets/apks/fdroid.apk",
         ["https://github.com/f-droid/fdroidclient/releases/download/1.18.0/org.fdroid.fdroid_1018050.apk",
          "https://f-droid.org/F-Droid.apk"]),
    ]

    def __init__(self, waydroid: Waydroid, config, parent=None):
        super().__init__(parent)
        self.waydroid = waydroid
        self.config = config
        self.setWindowTitle(tr("dlg_market"))

        root = QVBoxLayout(self)
        root.addWidget(QLabel(tr("market_choose")))
        for name, pkg, local, url in self.ITEMS:
            b = QPushButton(tr("market_install").format(name))
            b.clicked.connect(lambda _, n=name, p=pkg, l=local, u=url: self._install(n, p, l, u))
            root.addWidget(b)
        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        root.addWidget(close)

    def _install(self, name: str, pkg: str, local_rel: str, urls: list[str]) -> None:
        """本地资产优先，其次 URL 列表（后台探测+下载，全程不阻塞 UI）。"""
        local = self._find_asset(local_rel)
        if local:
            logger.info("使用内置资产: %s", local)
            self._do_install(name, pkg, local)
            return
        if self.config.mock:
            logger.info("下载安装(%s): %s - mock", name, urls)
            self._toast_done(name)
            return
        self._download_and_install(name, pkg, urls)

    def _set_busy(self, busy: bool) -> None:
        """下载/安装期间禁用全部按钮，防止重复点击。"""
        for b in self.findChildren(QPushButton):
            b.setEnabled(not busy)

    def _download_and_install(self, name: str, pkg: str, urls: list[str]) -> None:
        """网络路径：后台线程下载（可取消），UI 保持响应。"""
        self._set_busy(True)
        progress = QProgressDialog(tr("market_downloading").format(name), "取消", 0, 0, self)
        progress.setWindowTitle(tr("download"))
        progress.setMinimumDuration(0)
        progress.setStyleSheet("QProgressDialog{background:#151b33;color:#fff;}")
        worker = _MarketWorker(pkg, urls)
        progress.canceled.connect(worker.cancel)
        worker.finished.connect(
            lambda ok, path, err, pr=progress: self._on_download_done(
                name, pkg, ok, path, err, pr))
        worker.start()
        progress.exec_()  # 嵌套事件循环：线程下载期间界面照常响应
        self._set_busy(False)  # 取消竞态兜底（正常路径在槽里已恢复）

    def _on_download_done(self, name: str, pkg: str, ok: bool,
                          apk_path: str, err: str, progress) -> None:
        progress.close()
        if not ok:
            self._set_busy(False)
            if err != tr("market_cancel"):
                QMessageBox.warning(self, tr("market_download_fail"),
                                    tr("market_download_fail_msg").format(name, err))
            return
        self._do_install(name, pkg, apk_path)  # 按钮保持禁用直到安装结束

    def _find_asset(self, rel: str) -> str | None:
        """按相对路径找内置资产：打包目录 / 源码树 / 运行目录 / 配置目录。"""
        import sys
        candidates: list[Path] = []
        if getattr(sys, "_MEIPASS", None):  # PyInstaller 解包目录
            candidates.append(Path(sys._MEIPASS))
        candidates.append(Path(__file__).resolve().parents[2])  # 源码树
        candidates.append(Path.cwd())  # 部署目录（tview-app/）
        candidates.append(Path("~/.config/tview").expanduser())
        for base in candidates:
            p = base / rel
            if p.exists():
                return str(p)
        return None

    def _do_install(self, name: str, pkg: str, apk_path: str) -> None:
        """后台安装（waydroid app install 最长 60s，不能在 UI 线程跑）。"""
        progress = QProgressDialog(tr("market_installing").format(name), None, 0, 0, self)
        progress.setWindowTitle(tr("install"))
        progress.setMinimumDuration(0)
        progress.setStyleSheet("QProgressDialog{background:#16213e;color:#fff;}")
        worker = _InstallWorker(self.waydroid, apk_path)
        worker.finished.connect(
            lambda ok, err, pr=progress: self._on_install_done(name, ok, err, pr))
        worker.start()
        progress.exec_()
        self._set_busy(False)  # 取消/异常竞态兜底

    def _on_install_done(self, name: str, ok: bool, err: str, progress) -> None:
        progress.close()
        self._set_busy(False)
        if ok:
            self._toast_done(name)
        else:
            QMessageBox.warning(self, tr("market_install_fail"),
                                tr("market_install_fail_msg").format(name, err or ""))

    def _toast_done(self, name: str) -> None:
        if self.parent():
            self.parent()._toast(tr("toast_install_done").format(name))
