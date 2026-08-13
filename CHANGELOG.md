# Changelog

## [0.4.1] - 2026-08-13

设置页键鼠操控修复（BETA 0.4.1，桌面/远程桌面场景）。

### 修复
- **设置页鼠标支持**：点左侧分类切页；点选项行选中、点开关/动作行直接执行（与 OK 键同语义）；行/按钮加 hover 反馈
- **底部导航按钮**：右下角常驻「‹ 返回上一层」（右栏→左栏→退出，与返回键一致）和「✕ 退出设置」两个按钮，鼠标可点、遥控器可导航到
- **键盘/遥控器到达按钮区**：右栏末行 Down / 首行 Up 可进入按钮区（此前行列表循环，永远到不了）；按钮区左右键回右栏、OK 触发、返回键逐级退出
- **子对话框按键被吞**：设置页全局过滤器会吃掉 U盘/软件安装/按键映射等子对话框的返回/回车键 → 子对话框打开时放行按键（返回键由主窗口兜底关闭）
- **U盘安装对话框美化**：深色主题 + 最小宽度（原默认白底小窗在 TV 上不醒目）
- 设置页提示文案更新（注明鼠标可点击）

### 验证
- 开发机：冒烟测试 35/35；设置页键鼠全链路场景测试（按钮区导航/鼠标点分类/点开关/点退出/点 option 行）与子对话框弹出/Back 关闭测试全部通过

## [0.4.0-beta.1] - 2026-08-12

BETA 0.4：**UI 全面重做（安卓 TV 范式）+ 交互修复**。

### UI 重构（针对遥控器，解决"设置卡死/无法滚动/难操控"）
- **主界面导航移到顶部**：设置/软件安装/退出盒子/电源 从底部 Dock 移到顶部导航行；
  返回键把焦点切到导航行（安卓 TV launcher 手感）；上下键在导航行与网格间移动
- **设置页全屏重写**（弃用长条弹窗）：左分类右内容（显示/输入/应用/系统/安全/关于）；
  全部遥控器友好控件（选项行左右改值、开关行 OK 切换、动作行 OK 进入）；
  上下移动、左右切换/改值、OK 确认、返回逐级退出；不再有下拉框
- **风险说明内置**：安全相关选项下方直接写明风险（免密/锁屏/唤醒联动等）
- "应用下载"改名 **"软件安装"**（当贝/F-Droid/U 盘三合一，U 盘入口并入）

### 新功能
- **U 盘自动挂载到安卓**（设置开关，默认关）：bind /media 进 Waydroid 容器，安卓文件管理器可访问；
  sudoers 白名单 + tview-usbmount.sh（幂等）
- **应用退出后返回 TVIEW**（设置开关，默认开）：Linux 应用进程退出即回主界面；
  安卓应用回到安卓桌面（容器前台轮询）自动回 TVIEW
- **显示器唤醒联动**：唤醒功能开启时自动禁用 GNOME 闲置锁屏（否则锁屏挡住 TVIEW，
  修复"开显示器看到锁屏"问题）

### 修复
- 设置弹窗无法滚动（原 QDialog 无滚动区）→ 全屏页无此问题
- 语言/主题下拉框卡死遥控器（QComboBox popup 与方向键冲突）→ 改为选项行左右切换

### 验证
- 开发机：冒烟测试 35/35（导航模型/设置视图/新功能断言）
- VM（Ubuntu 26.04）：冒烟 29/29、设置视图启动正常

### 已知问题
- 安卓应用"退出回 TVIEW"依赖容器前台轮询（5 秒粒度，20 分钟上限）
- U 盘挂载需 Waydroid 重启生效（开关会提示）
- 旧 SettingsDialog 保留但不再使用（open_settings 走全屏视图）

## [0.3.0-beta.1] - 2026-08-12

BETA 0.3：**显示器唤醒 TVIEW**——桌面模式下检测到显示器开启，自动进入 TVIEW。

### 新增
- **显示器唤醒 TVIEW**（设置 → 显示器唤醒 TVIEW，默认开）：
  - 开关关闭则完全禁用
  - 唤醒方式两种：**任意显示器**开启即唤醒 / **仅特定显示器**唤醒（勾选列表）
  - 显示器识别：Linux DRM 层（`/sys/class/drm`），**接口无关**——HDMI/DP/VGA/DVI/USB-C 等所有接口统一检测
  - 检测机制：udev DRM 事件监听 + 状态轮询兜底（dpms Off→On / disconnected→connected 均视为"开启"）
  - 显示器列表显示接口 + 厂商型号（EDID 解析），勾选保存到配置
- **后台监听模式** `tview --watch`：桌面模式自启（tview-watch.desktop），无 UI 常驻；
  TVIEW 已在运行时不重复启动；盒子模式（labwc）不读 autostart，天然不冲突
- 安全兼容：不绕过任何认证（锁屏时启动的 TVIEW 解锁后可见）；L1/L2 安全模型不变

### 验证
- 开发机：冒烟测试 33/33；watch 启动、触发匹配逻辑（命中/未命中/any/关闭）单测通过；EDID 解析模块就位
- VM（Ubuntu 26.04）：冒烟 29/29、watch 启动正常

### 已知问题
- 识别"特定显示器"需显示器处于开启状态（EDID 可读时）；关机状态的显示器在列表中不可见
- 极少数只进 DPMS 睡眠且不触发任何事件的显示器，依赖轮询兜底（默认 30 秒内可检测）

## [0.2.0-beta.1] - 2026-08-12

BETA 0.2：**L2 盒子模式（kiosk）落地**，安全模型升级为"遥控器唯一入口"。

### 新增
- **L2 kiosk 会话**：labwc 合成器 + TVIEW 专用会话（`/usr/share/wayland-sessions/tview.desktop`），开机直达 TVIEW，无桌面环境；退出盒子回登录界面（要密码）
- **运行模式选择**（设置里可切换）：盒子模式 / 桌面模式（GNOME+自启）/ 正常登录——底层切换 GDM autologin 会话（tview-autologin.sh 扩展 `on|off|status [gnome|tview]`）
- **VNC 远程**（wayvnc）：盒子模式自动启动，监听 `0.0.0.0:5900`，局域网 VNC 客户端可看可操作；`vnc_password` 可设密码
- **窗口切换**：labwc 下回主页用 `wlrctl window focus tview`（app_id 匹配，实测通过）
- **安装器交互**：询问是否开机自启（默认开）与运行模式（默认盒子）；`--no-ask`/`--desktop-mode`/`--no-autostart` 参数覆盖
- 安装器装 labwc/wayvnc；英文 LOGO 去掉 "QiShi" 拼音（en 标题改为 TVIEW）
- 文档中英双版：README.en.md / RELEASE_NOTES.en.md；版本号 `0.2.0-beta.1`

### 技术选型
- cage 合成器在 headless 后端触发 wlr_xdg_surface 断言崩溃 → **改用 labwc 0.9.3**（窗口管理完善、wlrctl focus 实测通过）
- 远程方案：RustDesk 在 kiosk 会话不可用 → wayvnc（wlroots 原生 VNC）

### 验证
- 开发机：labwc+wayvnc+窗口切换实测；冒烟测试 30/30
- VM（Ubuntu 26.04）：安装器全流程、盒子模式配置、VNC 局域网握手、模式切换 3 态、冒烟 29/29

### 已知问题
- VNC 远程输入在无 GPU 虚拟机（headless 缺 virtual-pointer 协议）不可用，真实硬件正常
- 其余同 0.1.0-beta.1

## [0.1.0-beta.1] - 2026-08-12

BETA 首个可发布版本。功能完备、冒烟测试 30/30，安装器重构为"引导下载"模式（不捆绑第三方专有资产）。

### 新增
- 开机自启 BUG 修复：启动时按配置同步 autostart 文件（此前默认开启但文件从未写入，开机不生效）
- 设置里新增"关于"弹窗，显示版本号与项目信息
- **退出盒子默认锁屏**（安全）：设置新增"退出盒子后免密进入桌面"开关（默认关）；关闭时退出盒子自动锁屏（loginctl lock-session），需密码进桌面，防止免密会话被他人利用
- **应用菜单入口**：部署 TVIEW 图标 + `~/.local/share/applications/tview.desktop`，GNOME 应用列表可见可启动（修复退出后找不到入口的问题）
- 版本号 `0.1.0-beta.1`

### 安装器重构（scripts/install.sh）
- 全流程覆盖：系统层（binder/input 组/sudoers 白名单/udev）→ Waydroid → ARM 兼容层 → keyd → 部署 tview → 内置 APK → 安卓音量初始化 → 开机免密 → 开机自启 → 验收
- 版权合规：libhoudini / 商业 APK 不入仓库，安装时引导用户获取（waydroid_script 或本地资产）
- keyd 配置更新为实测键位版（158=back / 172=home / 127=menu / 14=backspace / 111=delete + 媒体键）

### 安装器修复（2026-08-12 干净机验收发现）
- **waydroid 源硬编码 noble → 动态检测发行版代号**（Ubuntu 26.04 需 resolute 源，否则 python3-gbinder 依赖冲突装不上）
- 修复 3 处误报成功：waydroid 安装检查（command -v）、tview 二进制复制后验证可执行、waydroid init 失败明确提示
- 二进制查找 `-x` 对目录误判 → `-f`；Release 下载改 `tview-bin` 防与包目录冲突
- 干净机验收：安装器 11 步全流程通过，冒烟测试 29/29
### CI 修复
- PyQt5 改用 pip 安装（apt 系统包与 setup-python 的 Python 不互通）
- smoke_test 环境容错：desktop 缓存 None/0 均视为正常
- 修复 volume_mock 日志格式化（% 风格与 {} 词条不匹配）
- Release 步骤补 `permissions: contents: write`

### 基础设施
- git 仓库化：.gitignore（排除第三方资产与构建产物）、README、MIT LICENSE、本文件
- GitHub Actions：自动构建单文件二进制 + 冒烟测试，打 tag 自动发布 Release

### 已知问题（随版本发布）
- **VM/无 GPU 环境**：Android surfaceflinger 需要 GPU，虚拟机（virgl 3D GL 能力不完整）里 Android 桌面可能起不来；真实硬件无此问题，虚拟机用户可尝试显卡直通
- 长按返回 3 秒在安卓应用聚焦时不生效（简化处理，安卓返回键可用）
- Waydroid "启动"按钮在 GNOME 桌面环境可能失败，盒子模式（autologin）下正常
- F-Droid 走 GitHub 直链，国内网络不稳时依赖内置 APK / U 盘安装

## [0.0.x] - 2026-08-08 ~ 2026-08-09（开发期，未发布）

- 阶段 1 原型：全屏网格启动器 + 遥控器 grab/ungrab + Waydroid 应用管理 + mock 模式
- 真机实测：遥控器全键位地图、音量问题真相（安卓内部 5/15）、ARM 兼容层来源确认
- keyd 系统驱动方案落地（解决 Waydroid 内返回/主页/音量失灵）
- UI 迭代：主题系统（5 主题 + 自定义）、WCAG 对比度保障、多语言、Dock 自动隐藏
- 修复：F-Droid 下载卡死主线程、设置按钮 NameError、网格偶发清空、对话框黑字蓝底对比度
