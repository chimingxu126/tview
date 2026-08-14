# AI 编程指令集 —— 启视·TVIEW Launcher v0.1

## 项目概述
你是一个经验丰富的 Linux 系统开发者，请用 Python 3.10 + PyQt5 编写一个名为 "启视·TVIEW Launcher" 的电视盒子启动器，运行在 Ubuntu 24.04 LTS（Wayland 会话）上。

## 核心要求

### 1. 程序架构
- 主入口：`main.py`，接收 `--prod`（生产）和 `--mock`（模拟）两个参数
- Mock 模式下：所有系统命令（如 `systemctl`、`waydroid`、`wget`）仅打印日志，不实际执行
- Prod 模式下：真实调用系统命令

### 2. 开机自启（Systemd）
- 服务文件路径：`/etc/systemd/system/tview-launcher.service`
- 启动后自动执行：
  1. 关闭 GDM（`systemctl stop gdm`）
  2. 启动 Cage 合成器（`cage -- /usr/bin/python3 /opt/tview/main.py --prod`）
  3. 后台启动 Waydroid 会话（`waydroid session start`）

### 3. 主界面（PyQt5）
- 全屏无边框，深色背景（#1a1a2e），可自定义壁纸
- **顶部状态栏**：左中右布局
  - 左侧：当前日期（格式：2026年7月30日 星期四）
  - 右侧：当前时间（格式：14:30）、网络状态图标（有线/WiFi/断开）
- **网格布局**：默认 3 列，可调范围 2~6 列（在设置中调节）
- **底部两个固定按钮**："⚙️ 设置" 和 "📦 应用下载"
- **焦点导航**：键盘方向键移动高亮框，回车键确认，ESC 返回

### 4. 应用管理
- **安卓应用**：通过 `waydroid app list` 获取包名列表，图标从 `~/.local/share/waydroid/data/icons/` 读取
- **Linux 应用**：从 `~/.config/tview/linux_apps.json` 读取自定义列表
- 启动安卓应用：`waydroid app launch 包名`
- 启动 Linux 应用：`subprocess.Popen(命令)`

### 5. 应用下载（市场）
内置以下市场，点击后逻辑一致（检测→下载→安装→刷新）：
- **当贝市场**（推荐中国用户）：`http://znds.tvapk.com/update/dbmarket.apk`，包名 `com.dangbei.tvlauncher`
- **F-Droid**：`https://f-droid.org/F-Droid.apk`，包名 `org.fdroid.fdroid`
- **Google Play**：从 APKMirror 获取官方签名版
- **Kodi**（推荐媒体中心）：官方 APK，包名 `org.xbmc.kodi`
- **VLC**（轻量播放器）：官方 APK，包名 `org.videolan.vlc`

> 下载时显示进度条，安装完成后自动刷新主界面图标列表。

### 6. 设置界面（完整功能清单）

| 模块 | 功能 |
|------|------|
| **节能模式** | 这是一个开关，**默认状态是「关闭」**，用户主动打开后才会生效。开启后：进入盒子模式时执行 `systemctl stop gdm` 杀死 Ubuntu 桌面；退出盒子模式时执行 `systemctl start gdm` 复活 Ubuntu 桌面。 |
| **桌面列数** | 滑块或左右键调节，范围 2~6 列，默认 3 列，调整后界面网格**立即重新布局**，不需要重启程序。 |
| **自定义壁纸** | 用户选择本地图片（PNG/JPG），程序读取后设为桌面背景，图片路径保存到配置文件 `~/.config/tview/config.yaml`。 |
| **自定义 Linux 应用** | 用户添加自定义应用，需要填写三个字段：应用名称、启动命令、图标路径。添加到列表后，主界面网格中会出现该应用的图标，点击执行 `subprocess.Popen(命令)` 启动。支持删除已有条目。 |
| **开机自启开关** | 控制 Systemd 服务是否开机自启。开启：`systemctl enable tview-launcher.service`；关闭：`systemctl disable tview-launcher.service`。 |
| **启动时执行（钩子）** | 多行文本框，用户填写 Shell 命令（如 `docker start jellyfin`）。程序进入主界面**之前**执行这些命令。默认留空，表示不执行任何命令。执行结果写入 `~/.config/tview/logs/hooks.log`。如果用户首次填写并保存，需要弹窗提示：“您已开启自定义钩子命令，该功能可能执行高危操作，请确保您了解每条命令的作用。” |
| **退出时执行（钩子）** | 多行文本框，用户填写 Shell 命令（如 `docker stop transmission`）。程序退出盒子模式**之前**执行这些命令。默认留空。执行结果写入 `~/.config/tview/logs/hooks.log`，超时保护 60 秒。 |
| **退出电视盒子** | 点击后关闭程序，回到 Ubuntu 桌面。如果节能模式是「开启」状态，则先执行 `systemctl start gdm` 复活桌面，再退出程序。 |
| **重启 / 关机** | 两个独立按钮，分别执行 `sudo reboot` 和 `sudo shutdown -h now`。点击前需要弹窗二次确认。 |
| **分辨率自适应** | 程序启动时通过 `xrandr` 获取显示器最佳分辨率并自动全屏适配。同时提供一个备选手动切换列表（720p / 1080p / 4K），供特殊显示器使用。 |
| **USB 唤醒** | 开关，默认关闭。用户开启后，程序自动识别当前插在电脑上的 USB 遥控器设备（通过 `lsusb` 获取 VID/PID），然后创建 UDEV 规则文件 `/etc/udev/rules.d/99-tview-wakeup.rules`，将 `power/wakeup` 设为 `enabled`，使电脑从睡眠状态被遥控器唤醒。 |
| **网络配置（IP/掩码/网关/DNS）** | 通过 `nmcli` 管理网络连接。支持 DHCP（自动）和手动两种模式。手动模式下，用户填写 IP 地址、子网掩码、网关、DNS。点击“应用”后执行 `nmcli con mod "连接名" ipv4.addresses ...` 和 `nmcli con up "连接名"`。修改后自动检测网络连通性（`ping 8.8.8.8`），并返回成功/失败反馈。 |
| **代理设置** | 支持 HTTP / HTTPS / SOCKS5 三种类型。用户填写代理地址、端口、用户名（可选）、密码（可选）。提供“测试连接”按钮，尝试通过代理访问 `https://api.ip.sb/ip`，返回连接成功或失败。开启后，程序中的 `wget` 下载和 `requests` 请求都走代理环境变量。 |
| **WiFi 切换** | 进入 WiFi 页面后自动扫描附近 WiFi 列表（通过 `nmcli dev wifi list`），显示 SSID、信号强度、加密方式。用户用遥控器选中一个 WiFi，按确认后弹出虚拟键盘输入密码，点击连接。连接成功或失败都有界面反馈。支持“忘记网络”功能。 |
| **定时关机** | 下拉选择或左右键选择：30分钟 / 1小时 / 2小时 / 关闭（默认）。用户设定后，程序后台启动倒计时，时间到执行 `sudo shutdown -h now`。取消定时关机则清空计时器。 |
| **屏保设置** | 下拉选择：无操作后 5分钟 / 10分钟 / 30分钟 启动屏保。屏保内容为：全屏显示当前时间（大号数字时钟）或纯黑屏。用户按遥控器任意键即退出屏保。默认关闭（不启用屏保）。 |
| **应用分类** | 在主界面顶部或侧边栏显示分类标签：全部 / 影音 / 游戏 / 工具 / 儿童。用户可以在设置中为每个应用手动分配分类标签，保存后主界面按分类过滤显示。默认所有应用在“全部”分类中。 |
| **日志导出** | 点击按钮后，程序将 `~/.config/tview/logs/` 目录下的所有日志文件（`tview.log`、`crash.log`、`hooks.log`）打包为 `tview-logs-日期.tar.gz`，保存到用户桌面，并弹窗提示“日志已导出到桌面”。 |

### 7. 遥控器输入模块（evdev）
- 自动检测 USB 2.4G 遥控器和游戏手柄
- 调用 `dev.grab()` 独占设备
- 支持设备：USB 2.4G 遥控器、蓝牙遥控器、Xbox/PS/Nintendo 手柄
- 按键映射表（含遥控器 + 手柄）：

| 功能 | 遥控器按键 | Xbox 手柄 | PS 手柄 | Nintendo 手柄 |
|------|-----------|-----------|---------|---------------|
| 确认 | KEY_ENTER | A 键 | × 键 | A 键 |
| 返回 | KEY_BACKSPACE | B 键 | ○ 键 | B 键 |
| 菜单 | KEY_MENU | X 键 | □ 键 | Y 键 |
| 主页 | KEY_HOME | Y 键 | △ 键 | X 键 |
| 方向 | KEY_UP/DOWN/LEFT/RIGHT | 十字键/左摇杆 | 十字键/左摇杆 | 十字键/左摇杆 |
| 音量+ | KEY_VOLUMEUP | 无 | 无 | 无 |
| 音量- | KEY_VOLUMEDOWN | 无 | 无 | 无 |

- **组合键（急救）**：长按返回键 3 秒 → 强制执行 `waydroid session stop` 并回到主界面

### 8. 钩子命令执行逻辑
- 在程序进入主界面之前执行"启动时执行"的命令
- 在程序退出之前执行"退出时执行"的命令
- 执行结果写入 `~/.config/tview/logs/hooks.log`
- 设置超时保护（60 秒），超时则强制停止并记录
- 安全措施：默认留空，首次启用弹窗提示风险

### 9. 看门狗（Watchdog）
- 独立线程运行，每 30 秒检测一次 Waydroid 是否可响应
- 连续检测 3 次失败 → 自动重启 Waydroid 会话
- 连续重启 3 次失败 → 自动退出盒子模式，回到 Ubuntu 桌面

### 10. 日志与调试
- 日志目录：`~/.config/tview/logs/`
- 日志文件：`tview.log`（滚动，最大 10MB）
- 异常日志：自动写入 `crash.log`，包含堆栈信息
- **日志导出功能**：设置页一键导出全部日志到用户桌面，方便反馈问题

### 11. 虚拟键盘组件（通用）
为 WiFi 密码输入等场景设计，遥控器可操作：
- 字母（大小写切换）
- 数字
- 常用符号
- 退格 / 清空 / 确认

### 12. 安装脚本（install.sh）
必须包含：
- 安装 Python 依赖：`PyQt5`、`evdev`、`pyyaml`
- 安装系统依赖：`waydroid`、`cage`、`ethtool`、`adb`、`nmcli`
- 创建配置文件目录 `~/.config/tview/`
- 注册 Systemd 服务
- 将当前用户加入 `input` 组（遥控器权限）
- **询问是否安装 Kodi**（可选）
- 输出安装完成提示

## 输出要求
- 生成完整的 Python 代码文件（按模块拆分）
- 所有类和方法必须有中文注释
- 配置文件使用 YAML 格式
- 安装脚本为 Bash 脚本
- Systemd 服务文件为 .service 格式