# Changelog

## [0.1.0-beta.1] - 2026-08-12

BETA 首个可发布版本。功能完备、冒烟测试 30/30，安装器重构为"引导下载"模式（不捆绑第三方专有资产）。

### 新增
- 开机自启 BUG 修复：启动时按配置同步 autostart 文件（此前默认开启但文件从未写入，开机不生效）
- 设置里新增"关于"弹窗，显示版本号与项目信息
- 版本号 `0.1.0-beta.1`

### 安装器重构（scripts/install.sh）
- 全流程覆盖：系统层（binder/input 组/sudoers 白名单/udev）→ Waydroid → ARM 兼容层 → keyd → 部署 tview → 内置 APK → 安卓音量初始化 → 开机免密 → 开机自启 → 验收
- 版权合规：libhoudini / 商业 APK 不入仓库，安装时引导用户获取（waydroid_script 或本地资产）
- keyd 配置更新为实测键位版（158=back / 172=home / 127=menu / 14=backspace / 111=delete + 媒体键）

### 基础设施
- git 仓库化：.gitignore（排除第三方资产与构建产物）、README、MIT LICENSE、本文件
- GitHub Actions：自动构建单文件二进制 + 冒烟测试，打 tag 自动发布 Release

### 已知问题（随版本发布）
- 长按返回 3 秒在安卓应用聚焦时不生效（简化处理，安卓返回键可用）
- Waydroid "启动"按钮在 GNOME 桌面环境可能失败，盒子模式（autologin）下正常
- F-Droid 走 GitHub 直链，国内网络不稳时依赖内置 APK / U 盘安装
- 安装器尚未在干净机器上做清空重装验收（待 VM 验证）

## [0.0.x] - 2026-08-08 ~ 2026-08-09（开发期，未发布）

- 阶段 1 原型：全屏网格启动器 + 遥控器 grab/ungrab + Waydroid 应用管理 + mock 模式
- 真机实测：遥控器全键位地图、音量问题真相（安卓内部 5/15）、ARM 兼容层来源确认
- keyd 系统驱动方案落地（解决 Waydroid 内返回/主页/音量失灵）
- UI 迭代：主题系统（5 主题 + 自定义）、WCAG 对比度保障、多语言、Dock 自动隐藏
- 修复：F-Droid 下载卡死主线程、设置按钮 NameError、网格偶发清空、对话框黑字蓝底对比度
