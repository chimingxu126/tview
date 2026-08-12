# Changelog

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
