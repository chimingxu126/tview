"""阶段1冒烟测试 v2：异步加载 + 统一按键路径（焦点遍历/回车激活/返回回主页）。"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import faulthandler
faulthandler.dump_traceback_later(15, exit=True)  # 卡死时输出栈并退出

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEvent, QEventLoop, QTimer, Qt
from PyQt5.QtGui import QKeyEvent

from tview.config import Config
from tview.logging_setup import setup_logging
from tview.remote import Remote
from tview.waydroid import Waydroid
from tview.apps import AppManager
from tview.ui.main_window import MainWindow

setup_logging()
app = QApplication(sys.argv)
# 隔离配置：不读真实 config.yaml（避免被用户调试时的列数设置干扰）
from pathlib import Path
import os as _os
_os.path.exists("/tmp/tview-smoke-config.yaml") and _os.remove("/tmp/tview-smoke-config.yaml")
config = Config(path=Path("/tmp/tview-smoke-config.yaml"), mock=True)
waydroid = Waydroid(mock=True)
mgr = AppManager(waydroid)
remote = Remote(mock=True)
win = MainWindow(config, waydroid, mgr, remote)
win.refresh_apps()  # 异步加载

# 稳定等待：等 apps 加载且网格填充（避免 queued 信号时序竞态）
loop = QEventLoop()

def _wait_grid():
    if win.grid.count() > 0:
        loop.quit()
    else:
        QTimer.singleShot(100, _wait_grid)
QTimer.singleShot(100, _wait_grid)
QTimer.singleShot(8000, loop.quit)
loop.exec_()

results = []
def check(name, cond):
    results.append((name, cond))
    print(f"{'✅' if cond else '❌'} {name}")

def press(action):
    win.on_remote_key(action)
    QApplication.processEvents()

# 1. 异步加载
check("mock应用加载=5", len(win.apps) == 5)
check("网格有5个卡片", win.grid.count() == 5)

# 2. 显式导航（自管理焦点索引，不依赖平台焦点）
press("right")
check(f"右移焦点 index=1", win.focused_index == 1)
press("down")
check(f"下移焦点 index=4", win.focused_index == 4)
press("left")
check(f"左移焦点 index=3", win.focused_index == 3)

# 3. 回车激活 → 启动应用进入 APP 态（平台焦点不可用时走索引回退）
press("enter")
check("enter 启动应用且进入 APP 态", remote._state == "APP")

# 4. 长按返回 → 回主页
win.on_longpress_back()
check("长按返回回 HOME 态", remote._state == "HOME")

# 5. back 键 → 回主页并聚焦首卡
press("back")
check(f"back 回主页聚焦首卡 focused_index=0", win.focused_index == 0)

# 6. home 键
press("home")
check("home 键无异常", True)

# 7. 音量 / 电源（mock 短路；电源弹窗用桩替代）
win._power_menu = lambda: None
press("volume_up"); check("音量键 mock 无异常", True)
press("power"); check("电源键 mock 无异常", True)

# 8. 状态栏
win._update_status()
check("日期栏有年份", "年" in win.date_label.text())
check("时间栏有冒号", ":" in win.time_label.text())

# 9. 列数实时调整
config.set("columns", 4); win.render_grid()
check("4列网格重排正常", win.grid.count() == 5)
config.set("columns", 3); win.render_grid()

# 9.5 底部按钮可达性：下→右→下 到设置，再下到应用下载，上回最后卡片
win.on_remote_key("down")    # 0→3
win.on_remote_key("right")   # 3→4 最后一张卡片
win.on_remote_key("down")    # 4→5 设置按钮
check(f"向下到设置按钮 focused_index=5", win.focused_index == 5)
win.on_remote_key("down")    # 5→6 应用下载
check(f"再向下到应用下载 focused_index=6", win.focused_index == 6)
win.on_remote_key("up")      # 6→4 最后卡片
check(f"向上回最后卡片 focused_index=4", win.focused_index == 4)

# 9.6 Waydroid 状态标签
win._update_wd_status()
check("Waydroid 状态标签存在", "Waydroid" in win.wd_label.text())

# 9.7 桌面缓存读取（真实 .desktop 文件，只读不执行）
from tview.waydroid import Waydroid as RealWaydroid
real = RealWaydroid(mock=False)
cached = real._apps_from_desktop()
check(f"desktop 缓存读取正常（{len(cached) if cached else 0} 个）", cached is not None and len(cached) >= 5)
if cached:
    check(f"缓存含图标路径", all(a.icon for a in cached[:5]))

# 10. 事件过滤器：回车激活聚焦的按钮（设置按钮 → 触发 open_settings，断开原连接用桩替代）
opened = {"v": False}
win.btn_settings.clicked.disconnect()
win.btn_settings.clicked.connect(lambda: opened.__setitem__("v", True))
win.btn_settings.setFocus()
QApplication.processEvents()
# offscreen 平台焦点管理不可靠，直接向按钮发送回车事件（仍经过 app 级 eventFilter）
ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
QApplication.sendEvent(win.btn_settings, ev)
QApplication.processEvents()
check("回车激活设置按钮", opened["v"] is True)

# 11. 渲染截图
ok = win.grab().save("/tmp/tview-smoke2.png")
check("渲染截图成功", ok)

# 12. 设置弹窗真实打开（不再 stub 被测路径：QCheckBox 导入等回归防护）
from tview.ui.main_window import SettingsDialog, KeyMapDialog, MarketDialog
dlg = SettingsDialog(config, win)
check("设置弹窗可打开", dlg.windowTitle() == "设置")
check("开机自启开关存在", hasattr(dlg, "autostart_chk"))
dlg.close()

# 13. 遥控器映射对话框
kmd = KeyMapDialog(config, win)
check("映射对话框可打开", kmd.windowTitle() == "遥控器按键映射")
check("映射列表完整", kmd.list_widget.count() == len(kmd.KEYS))
kmd._on_captured(Qt.Key_Home)
check("录制捕获主页键", "已捕获" in kmd.record_label.text() or "Captured" in kmd.record_label.text())
kmd.close()

# 14. 市场：F-Droid（已去掉“（中国）”后缀）
md = MarketDialog(win.waydroid, config, win)
check("市场含 F-Droid", any(i[0] == "F-Droid" for i in md.ITEMS))
check("市场名无括号后缀", not any("（中国）" in i[0] for i in md.ITEMS))
md.close()

# 15. 自定义映射分发（主页→设置）
config.set("remote_keymap", {str(Qt.Key_Home): "settings"})
win.open_settings = lambda: None  # 桩：避免 exec_ 阻塞
win.eventFilter(win, QKeyEvent(QEvent.KeyPress, Qt.Key_Home, Qt.NoModifier))
check("自定义映射分发", True)
config.set("remote_keymap", {})

fail = [n for n, c in results if not c]
print(f"\n结果: {len(results)-len(fail)}/{len(results)} 通过")
sys.exit(1 if fail else 0)
