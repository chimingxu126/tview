"""设置页全屏视图（安卓 TV 风格，BETA 0.4 重写）。

交互范式（完全遥控器友好）：
- 左栏分类 / 右栏选项；左右键切换栏或改值；上下键移动焦点
- OK 键：进入子页/切换开关/确认
- 返回键：右栏→左栏→退出设置（逐级回退）
- 全部自管理焦点，不依赖 Qt 平台焦点；无下拉框、无鼠标依赖

行类型：
- option  选项行：左右改值，即时保存（语言/主题/列数/模式/唤醒方式）
- switch  开关行：OK 或左右切换开/关
- action  动作行：OK 进入子对话框/子页面（按键映射/添加应用/U盘/市场/关于等）
- 每行可带 risk 说明文字（安全相关风险提示）
"""
from __future__ import annotations

import logging
import tarfile
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                             QStackedWidget, QVBoxLayout, QWidget)

from ..config import Config
from ..i18n import tr
from ..displays import label as disp_label
from ..displays import list_connectors
from ..theme import resolve_theme

logger = logging.getLogger(__name__)

FOCUS_QSS = (
    "QFrame#row{background:rgba(255,255,255,0.07);border-radius:12px;}"
    "QFrame#row:hover{background:rgba(255,255,255,0.12);}"
    "QFrame#row[focus=true]{background:rgba(255,255,255,0.16);"
    "border:2px solid #ffffff;}"
    "QFrame#row QLabel#rowName{font-size:22px;color:#eef2ff;border:none;background:transparent;}"
    "QFrame#row QLabel#rowValue{font-size:20px;color:#9db4e8;border:none;background:transparent;}"
    "QFrame#row QLabel#rowArrow{font-size:24px;color:#9db4e8;border:none;background:transparent;}"
    "QFrame#row QLabel#rowRisk{font-size:15px;color:#8a93ad;border:none;background:transparent;}"
    "QFrame#row[focus=true] QLabel#rowName{color:#ffffff;}"
    "QFrame#row[focus=true] QLabel#rowValue{color:#ffffff;}"
)

# 底部导航按钮（返回上一层 / 退出设置）：鼠标可点，遥控器/键盘可导航到
BTN_QSS = (
    "QPushButton#navBtn{background:rgba(255,255,255,0.08);color:#eef2ff;"
    "border:2px solid rgba(255,255,255,0.15);border-radius:14px;"
    "font-size:20px;padding:10px 28px;}"
    "QPushButton#navBtn:hover{background:rgba(255,255,255,0.16);border-color:#ffffff;}"
    "QPushButton#navBtn[focus=true]{background:rgba(255,255,255,0.22);"
    "border:2px solid #ffffff;}"
)


class Row(QFrame):
    """设置行：名称 + 当前值 + 箭头（动作行）+ 可选风险说明。

    鼠标左键点击行 = 选中 + 激活（与遥控器 OK 键同语义）。
    """

    clicked = pyqtSignal()

    def __init__(self, spec: dict, getter, setter, parent=None):
        super().__init__(parent)
        self.spec = spec
        self._get = getter
        self._set = setter
        self.setObjectName("row")
        self.setProperty("focus", False)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(14)
        self.name_lbl = QLabel(spec["label"])
        self.name_lbl.setObjectName("rowName")
        top.addWidget(self.name_lbl)
        top.addStretch(1)
        self.value_lbl = QLabel("")
        self.value_lbl.setObjectName("rowValue")
        top.addWidget(self.value_lbl)
        self.arrow_lbl = QLabel("»" if spec["type"] == "action" else "")
        self.arrow_lbl.setObjectName("rowArrow")
        top.addWidget(self.arrow_lbl)
        lay.addLayout(top)
        risk = spec.get("risk", "")
        if risk:
            rl = QLabel(risk)
            rl.setObjectName("rowRisk")
            rl.setWordWrap(True)
            lay.addWidget(rl)
        self.refresh()

    def refresh(self) -> None:
        """按当前配置刷新显示值。"""
        spec = self.spec
        if spec["type"] == "option":
            cur = self._get(spec["key"], spec.get("default"))
            mapping = spec.get("values", {})
            self.value_lbl.setText(mapping.get(str(cur), str(cur)))
            if spec.get("show_arrow", True):
                self.arrow_lbl.setText("‹ ›")
            else:
                self.arrow_lbl.setText("")
        elif spec["type"] == "switch":
            v = bool(self._get(spec["key"], spec.get("default", False)))
            self.value_lbl.setText(tr("on") if v else tr("off"))
            self.arrow_lbl.setText("")
        else:
            self.value_lbl.setText(spec.get("value", ""))
            self.arrow_lbl.setText("»")

    def set_focus(self, on: bool) -> None:
        self.setProperty("focus", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
            e.accept()
            return
        super().mousePressEvent(e)

    def activate(self) -> bool:
        """OK 键动作。返回 True=需要关闭设置页。"""
        spec = self.spec
        t = spec["type"]
        if t == "switch":
            v = bool(self._get(spec["key"], spec.get("default", False)))
            self._set(spec["key"], not v)
            self.refresh()
        elif t == "option":
            pass  # 左右键改值
        elif t == "action":
            cb = spec.get("cb")
            if cb:
                cb()
        return False


class SettingsView(QDialog):
    """全屏设置页：左分类 + 右内容，遥控器三键驱动。"""

    def __init__(self, config: Config, main_win=None):
        super().__init__()
        self.config = config
        self.main_win = main_win
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        # 主题背景（深色渐变，跟随当前主题配色）
        _t = resolve_theme(self.config)
        c1 = _t.get("bg1", "#101828")
        c2 = _t.get("bg2", "#16223c")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QDialog{{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {c1},stop:1 {c2});}}{FOCUS_QSS}{BTN_QSS}")
        self.side = "left"
        self.cat_idx = 0
        self.row_idx = 0
        self.btn_idx = 0
        global CATS
        CATS = _init_cats(self)
        self._build_ui()
        self._render()
        self.showFullScreen()
        QApplication.instance().installEventFilter(self)

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 20)
        root.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(24)

        left_box = QVBoxLayout()
        title = QLabel(tr("dlg_settings"))
        title.setStyleSheet("font-size:30px;font-weight:bold;color:#ffffff;")
        left_box.addWidget(title)
        left_box.addSpacing(12)
        self.cat_list = QListWidget()
        self.cat_list.setFrameShape(QFrame.NoFrame)
        self.cat_list.setStyleSheet(
            "QListWidget{background:transparent;border:none;font-size:20px;color:#aab4cc;}"
            "QListWidget::item{height:52px;padding-left:16px;border-radius:10px;}"
            "QListWidget::item:hover{background:rgba(255,255,255,0.10);}"
            "QListWidget::item:selected{background:rgba(255,255,255,0.16);color:#ffffff;}")
        self.cat_list.setFixedWidth(220)
        for cat in CATS:
            it = QListWidgetItem(cat["title"])
            self.cat_list.addItem(it)
        self.cat_list.itemClicked.connect(self._on_cat_clicked)
        left_box.addWidget(self.cat_list, 1)
        hint = QLabel(tr("settings_hint"))
        hint.setStyleSheet("font-size:14px;color:#8a93ad;")
        hint.setWordWrap(True)
        left_box.addWidget(hint)
        top.addLayout(left_box)

        self.stack = QStackedWidget()
        top.addWidget(self.stack, 1)
        root.addLayout(top, 1)

        # 底部导航按钮：返回上一层 / 退出设置（鼠标可点，遥控器可导航到）
        bar = QHBoxLayout()
        bar.setSpacing(14)
        bar.addStretch(1)
        self.btn_back = QPushButton(tr("nav_back"))
        self.btn_back.setObjectName("navBtn")
        self.btn_back.setProperty("focus", False)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self._back_step)
        self.btn_exit = QPushButton(tr("nav_exit"))
        self.btn_exit.setObjectName("navBtn")
        self.btn_exit.setProperty("focus", False)
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.clicked.connect(self._close_settings)
        bar.addWidget(self.btn_back)
        bar.addWidget(self.btn_exit)
        root.addLayout(bar)

    def _build_cat_page(self, cat: dict) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)
        hdr = QLabel(cat["title"])
        hdr.setStyleSheet("font-size:24px;color:#9db4e8;padding-bottom:4px;")
        lay.addWidget(hdr)
        rows = []
        for spec in cat["rows"]:
            row = Row(spec, self.config.get, self.config.set, page)
            row.clicked.connect(lambda r=row: self._on_row_clicked(r))
            rows.append(row)
            lay.addWidget(row)
        lay.addStretch(1)
        page._rows = rows
        return page

    def _render(self) -> None:
        if self.stack.count() == 0:
            self._pages = [self._build_cat_page(c) for c in CATS]
            for p in self._pages:
                self.stack.addWidget(p)
        self._apply_highlight()
        self.cat_list.setCurrentRow(0)

    # ---------------- 焦点 ----------------
    def _rows(self) -> list:
        return getattr(self.stack.currentWidget(), "_rows", [])

    def _apply_highlight(self) -> None:
        rows = self._rows()
        for i, r in enumerate(rows):
            r.set_focus(self.side == "right" and i == self.row_idx)
        # 左侧分类高亮
        for i in range(self.cat_list.count()):
            self.cat_list.item(i).setSelected(self.side == "left" and i == self.cat_idx)
        # 底部按钮高亮（btns 态）
        self.btn_back.setProperty("focus", self.side == "btns" and self.btn_idx == 0)
        self.btn_exit.setProperty("focus", self.side == "btns" and self.btn_idx == 1)
        for b in (self.btn_back, self.btn_exit):
            b.style().unpolish(b)
            b.style().polish(b)

    def _on_key(self, key: int) -> bool:
        rows = self._rows()
        if key in (Qt.Key_Up, Qt.Key_Down):
            d = 1 if key == Qt.Key_Down else -1
            if self.side == "left":
                n = self.cat_list.count()
                self.cat_idx = (self.cat_idx + d) % n
                self.stack.setCurrentIndex(self.cat_idx)
                self.row_idx = 0
            elif self.side == "right":
                if rows:
                    # 列表与底部按钮区双向可达：末行 Down→按钮区，首行 Up→按钮区
                    if key == Qt.Key_Down and self.row_idx == len(rows) - 1:
                        self.side = "btns"
                        self.btn_idx = 0
                    elif key == Qt.Key_Up and self.row_idx == 0:
                        self.side = "btns"
                        self.btn_idx = 1
                    else:
                        self.row_idx = (self.row_idx + d) % len(rows)
            else:  # btns
                self.btn_idx = (self.btn_idx + d) % 2
            self._apply_highlight()
            return True
        if key in (Qt.Key_Left, Qt.Key_Right):
            if self.side == "btns":
                self.side = "right"
            elif self.side == "left" and key == Qt.Key_Right:
                self.side = "right"
            elif self.side == "right" and key == Qt.Key_Left:
                self.side = "left"
            elif self.side == "right" and rows:
                r = rows[self.row_idx % len(rows)]
                if r.spec["type"] == "option":
                    self._change_option(r, -1 if key == Qt.Key_Left else 1)
                elif r.spec["type"] == "switch":
                    r.activate()
            self._apply_highlight()
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self.side == "left":
                self.side = "right"
            elif self.side == "right" and rows:
                rows[self.row_idx % len(rows)].activate()
            elif self.side == "btns":
                (self.btn_back if self.btn_idx == 0 else self.btn_exit).click()
            self._apply_highlight()
            return True
        if key in (Qt.Key_Back, Qt.Key_Backspace):
            if self.side == "right":
                self.side = "left"
            elif self.side == "btns":
                self.side = "right"
            else:
                self._close_settings()
            self._apply_highlight()
            return True
        if key == Qt.Key_Home:
            self._close_settings()
            return True
        return False

    # ---------------- 鼠标支持 ----------------
    def _on_row_clicked(self, row: Row) -> None:
        """鼠标点击行：选中 + 激活（switch/action 立即执行，option 仅选中）。"""
        rows = self._rows()
        if row not in rows:
            return
        self.side = "right"
        self.row_idx = rows.index(row)
        self._apply_highlight()
        if row.spec["type"] in ("switch", "action"):
            row.activate()

    def _on_cat_clicked(self, item) -> None:
        """鼠标点击左侧分类：切页。"""
        self.cat_idx = self.cat_list.row(item)
        self.stack.setCurrentIndex(self.cat_idx)
        self.row_idx = 0
        self.side = "left"
        self._apply_highlight()

    def _back_step(self) -> None:
        """返回上一层：右栏→左栏；左栏/按钮区→退出设置。"""
        if self.side in ("right", "btns"):
            self.side = "left"
            self._apply_highlight()
        else:
            self._close_settings()

    def _change_option(self, row: Row, delta: int) -> None:
        spec = row.spec
        vals = spec.get("values_ordered") or []
        if not vals:
            return
        cur = str(self.config.get(spec["key"], spec.get("default", "")))
        try:
            i = vals.index(cur)
        except ValueError:
            i = 0
        nxt = vals[(i + delta) % len(vals)]
        self.config.set(spec["key"], nxt)
        self.config.save()
        if spec.get("on_change"):
            spec["on_change"](nxt)
        row.refresh()

    def _close_settings(self) -> None:
        QApplication.instance().removeEventFilter(self)
        self.accept()

    # ---------------- 动作行回调 ----------------
    def _pick_wallpaper(self) -> None:
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, tr("theme_choose_wallpaper"), "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.config.set("wallpaper", path)
            self.config.save()
            if self.main_win:
                self.main_win.apply_theme()

    def _open_keymap(self) -> None:
        from .main_window import KeyMapDialog
        if self.main_win:
            KeyMapDialog(self.config, self.main_win).exec_()

    def _open_add_app(self) -> None:
        from .main_window import AddAppDialog
        if self.main_win:
            AddAppDialog(self.config, self.main_win).exec_()

    def _open_usb(self) -> None:
        from .main_window import UsbInstallDialog
        if self.main_win:
            UsbInstallDialog(self.main_win.waydroid, self.config, self.main_win).exec_()

    def _open_market(self) -> None:
        from .main_window import MarketDialog
        if self.main_win:
            MarketDialog(self.main_win.waydroid, self.config, self.main_win).exec_()

    def _wd_action(self, act: str) -> None:
        if not self.main_win:
            return
        wd = self.main_win.waydroid
        if act == "start":
            ok, err = wd.start()
            QMessageBox.information(self, tr("dlg_settings"),
                                    tr("wd_cmd_ok") if ok else (err or tr("wd_cmd_fail")))
        elif act == "stop":
            wd.stop()
            QMessageBox.information(self, tr("dlg_settings"), tr("wd_stop_ok"))
        elif act == "restart":
            wd.restart()
            QMessageBox.information(self, tr("dlg_settings"), tr("wd_restart_ok"))

    def _apply_mode(self, mode: str) -> None:
        if not self.main_win:
            return
        ok, err = self.main_win._apply_mode(mode)
        if ok:
            QMessageBox.information(self, tr("dlg_settings"), tr("mode_restart"))
        else:
            QMessageBox.warning(self, tr("dlg_settings"), err or tr("autologin_fail"))

    def _apply_autologin(self, v: bool) -> None:
        if not self.main_win:
            return
        ok, err = self.main_win._apply_autologin(v)
        if ok:
            QMessageBox.information(self, tr("dlg_settings"), tr("autologin_restart"))
        else:
            QMessageBox.warning(self, tr("dlg_settings"), err or tr("autologin_fail"))

    def _set_dw(self, key: str, val) -> None:
        dw = dict(self.config.get("display_wake") or {})
        dw[key] = val
        self.config.set("display_wake", dw)
        self.config.save()

    def _apply_usb_mount(self, v: bool) -> None:
        if self.main_win:
            self.main_win._apply_usb_mount()

    def _pick_dw_targets(self) -> None:
        """特定显示器多选（对话框列表，遥控器可操作）。"""
        from PyQt5.QtWidgets import QDialogButtonBox, QListWidgetItem as QLWItem
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("dw_targets"))
        lay = QVBoxLayout(dlg)
        lst = QListWidget()
        lst.setStyleSheet("font-size:20px;color:#eef2ff;background:rgba(255,255,255,0.06);")
        dw = dict(self.config.get("display_wake") or {})
        targets = set(dw.get("targets") or [])
        ons = [c for c in list_connectors() if c["on"]]
        if not ons:
            it = QLWItem(tr("dw_none_found"))
            it.setFlags(Qt.NoItemFlags)
            lst.addItem(it)
        for c in ons:
            it = QLWItem(disp_label(c))
            it.setData(Qt.UserRole, c["connector"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if c["connector"] in targets else Qt.Unchecked)
            lst.addItem(it)
        lay.addWidget(lst)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec_() == QDialog.Accepted:
            checked = [lst.item(i).data(Qt.UserRole) for i in range(lst.count())
                       if lst.item(i).checkState() == Qt.Checked and lst.item(i).data(Qt.UserRole)]
            dw["targets"] = checked
            self.config.set("display_wake", dw)
            self.config.save()

    def _export_logs(self) -> None:
        from ..config import LOG_DIR
        import shutil
        from datetime import datetime
        try:
            dst = f"/tmp/tview-logs-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
            with tarfile.open(dst, "w:gz") as tf:
                for f in Path(LOG_DIR).glob("*.log"):
                    tf.add(str(f), arcname=f.name)
            QMessageBox.information(self, tr("dlg_settings"), tr("logs_exported").format(dst))
        except Exception as e:
            QMessageBox.warning(self, tr("dlg_settings"), str(e))

    def _exit_box(self) -> None:
        if self.main_win:
            self._close_settings()
            self.main_win.exit_box()

    def _show_about(self) -> None:
        from .. import __version__
        QMessageBox.about(self, tr("app_title"),
                          f"{tr('app_title')} {__version__}\n\n"
                          f"{tr('about_line1')}\n{tr('about_line2')}\n\n{tr('about_line3')}")

    # ---------------- 事件 ----------------
    def eventFilter(self, obj, ev):
        if ev.type() == ev.Type.KeyPress:
            return self._on_key(ev.key())
        return False


# ---------------- 分类与行定义 ----------------
def _cat_display(config, view) -> dict:
    return {
        "title": tr("cat_display"),
        "rows": [
            {"type": "option", "key": "theme", "label": tr("theme"),
             "values_ordered": ["minimal", "aurora", "tech", "space", "bright", "custom"],
             "values": {"minimal": "Minimal", "aurora": "Aurora", "tech": "Tech",
                        "space": "Space", "bright": "Bright", "custom": tr("theme_custom")},
             "default": "minimal"},
            {"type": "option", "key": "columns", "label": tr("columns"),
             "values_ordered": ["2", "3", "4", "5", "6"],
             "values": {"2": "2", "3": "3", "4": "4", "5": "5", "6": "6"}, "default": "3",
             "on_change": lambda v: view.main_win.render_grid() if view.main_win else None},
            {"type": "action", "key": "wallpaper", "label": tr("wallpaper"),
             "cb": lambda: view._pick_wallpaper()},
        ],
    }


def _cat_input(config, view) -> dict:
    return {
        "title": tr("cat_input"),
        "rows": [
            {"type": "action", "key": "keymap", "label": tr("keymap_btn"),
             "cb": lambda: view._open_keymap()},
            {"type": "switch", "key": "wd_status_show", "label": tr("wd_status_show"),
             "default": True},
        ],
    }


def _cat_apps(config, view) -> dict:
    return {
        "title": tr("cat_apps"),
        "rows": [
            {"type": "action", "key": "add_app", "label": tr("add_linux_app"),
             "cb": lambda: view._open_add_app()},
            {"type": "action", "key": "usb", "label": tr("usb_install_btn"),
             "cb": lambda: view._open_usb()},
            {"type": "action", "key": "market", "label": tr("market"),
             "cb": lambda: view._open_market()},
            {"type": "switch", "key": "usb_mount", "label": tr("usb_mount"),
             "default": False, "risk": tr("usb_mount_risk"),
             "on_change": lambda v: view._apply_usb_mount(v)},
            {"type": "switch", "key": "app_exit_home", "label": tr("app_exit_home"),
             "default": True},
            {"type": "action", "key": "wd_start", "label": tr("wd_start"),
             "cb": lambda: view._wd_action("start")},
            {"type": "action", "key": "wd_stop", "label": tr("wd_stop"),
             "cb": lambda: view._wd_action("stop")},
            {"type": "action", "key": "wd_restart", "label": tr("wd_restart"),
             "cb": lambda: view._wd_action("restart")},
        ],
    }


def _cat_system(config, view) -> dict:
    return {
        "title": tr("cat_system"),
        "rows": [
            {"type": "option", "key": "language", "label": tr("language"),
             "values_ordered": ["zh", "en"], "values": {"zh": "中文", "en": "English"},
             "default": "zh", "show_arrow": False,
             "risk": tr("lang_restart")},
            {"type": "switch", "key": "autostart", "label": tr("autostart"), "default": True},
            {"type": "option", "key": "mode", "label": tr("mode"),
             "values_ordered": ["tview", "gnome", "off"],
             "values": {"tview": tr("mode_kiosk"), "gnome": tr("mode_desktop"), "off": tr("mode_normal")},
             "default": "gnome", "show_arrow": False,
             "risk": tr("mode_risk"),
             "on_change": lambda v: view._apply_mode(v)},
            {"type": "action", "key": "logs", "label": tr("export_logs"),
             "cb": lambda: view._export_logs()},
            {"type": "action", "key": "exit", "label": tr("exit_box"),
             "cb": lambda: view._exit_box()},
        ],
    }


def _cat_security(config, view) -> dict:
    return {
        "title": tr("cat_security"),
        "rows": [
            {"type": "switch", "key": "autologin", "label": tr("autologin"), "default": False,
             "risk": tr("autologin_risk"),
             "on_change": lambda v: view._apply_autologin(v)},
            {"type": "switch", "key": "exit_nopasswd", "label": tr("exit_nopasswd"),
             "default": False, "risk": tr("exit_nopasswd_risk")},
            {"type": "switch", "key": "dw_enabled", "label": tr("dw_enabled"), "default": True,
             "risk": tr("dw_risk"),
             "on_change": lambda v: view._set_dw("enabled", v)},
            {"type": "option", "key": "dw_mode", "label": tr("dw_mode"),
             "values_ordered": ["any", "specific"],
             "values": {"any": tr("dw_mode_any"), "specific": tr("dw_mode_specific")},
             "default": "any", "show_arrow": False,
             "on_change": lambda v: view._set_dw("mode", v)},
            {"type": "action", "key": "dw_targets", "label": tr("dw_targets"),
             "value": "…",
             "cb": lambda: view._pick_dw_targets()},
        ],
    }


def _cat_about(config, view) -> dict:
    from .. import __version__
    return {
        "title": tr("cat_about"),
        "rows": [
            {"type": "action", "key": "about", "label": tr("about"),
             "value": tr("app_title") + " " + __version__,
             "cb": lambda: view._show_about()},
        ],
    }


CATS = None  # 在 _init_cats() 里按 tr() 构建（i18n 已初始化）


def _init_cats(view) -> list:
    return [
        _cat_display(view.config, view),
        _cat_input(view.config, view),
        _cat_apps(view.config, view),
        _cat_system(view.config, view),
        _cat_security(view.config, view),
        _cat_about(view.config, view),
    ]
