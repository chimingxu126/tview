"""虚拟键盘组件（阶段1：字母/数字/常用符号，遥控器可操作）。

设计要点：
- 焦点跟随：方向键移动高亮，回车输入，退格删除
- 大小写切换、清空、确认
- 供 WiFi 密码等场景使用（阶段 1 先作为组件就绪）
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QVBoxLayout, QWidget)

ROWS = [
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
]


class VKeyboard(QDialog):
    """遥控器可操作的屏幕键盘。"""

    submitted = pyqtSignal(str)

    def __init__(self, title: str = "输入", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._shift = False
        self._keys: list[QPushButton] = []
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        self.input = QLineEdit()
        self.input.setStyleSheet("QLineEdit{font-size:22px;padding:8px;background:#16213e;color:#fff;border:1px solid #3a4a6b;}")
        root.addWidget(self.input)

        grid = QGridLayout()
        for r, row in enumerate(ROWS):
            for c, ch in enumerate(row):
                btn = self._make_key(ch)
                grid.addWidget(btn, r, c)
        # 功能行
        shift = self._make_key("⇧", special="shift")
        back = self._make_key("⌫", special="backspace")
        clear = self._make_key("清空", special="clear")
        ok = self._make_key("确定", special="ok")
        grid.addWidget(shift, 4, 0, 1, 2)
        grid.addWidget(back, 4, 2, 1, 3)
        grid.addWidget(clear, 4, 5, 1, 3)
        grid.addWidget(ok, 4, 8, 1, 3)
        root.addLayout(grid)

        self._focus_first()

    def _make_key(self, text: str, special: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("special", special)
        btn.setFocusPolicy(Qt.StrongFocus)
        btn.setStyleSheet(
            "QPushButton{font-size:20px;min-height:44px;background:#16213e;color:#fff;border:1px solid #3a4a6b;border-radius:6px;}"
            "QPushButton:focus{background:#e94560;border:2px solid #fff;}"
        )
        if special:
            btn.clicked.connect(lambda _, s=special: self._on_special(s))
        else:
            btn.clicked.connect(lambda _, t=text: self._type(t))
        self._keys.append(btn)
        return btn

    def _focus_first(self) -> None:
        if self._keys:
            self._keys[0].setFocus()

    def _type(self, ch: str) -> None:
        text = ch.upper() if self._shift and ch.isalpha() else ch
        self.input.setText(self.input.text() + text)
        self._shift = False

    def _on_special(self, special: str) -> None:
        if special == "shift":
            self._shift = not self._shift
        elif special == "backspace":
            self.input.setText(self.input.text()[:-1])
        elif special == "clear":
            self.input.clear()
        elif special == "ok":
            self.submitted.emit(self.input.text())
            self.accept()

    def keyPressEvent(self, event):
        """方向键导航 + 回车确认（键盘/遥控器统一走这里）。"""
        key = event.key()
        btn = self.focusWidget()
        if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
            if isinstance(btn, QPushButton):
                self._move_focus(btn, key)
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if isinstance(btn, QPushButton):
                btn.click()
            return
        if key == Qt.Key_Backspace:
            self._on_special("backspace")
            return
        super().keyPressEvent(event)

    def _move_focus(self, btn: QPushButton, key: int) -> None:
        """在网格里按方向移动焦点。"""
        idx = self._keys.index(btn)
        step = {Qt.Key_Right: 1, Qt.Key_Left: -1, Qt.Key_Down: 10, Qt.Key_Up: -10}[key]
        nxt = max(0, min(len(self._keys) - 1, idx + step))
        self._keys[nxt].setFocus()
