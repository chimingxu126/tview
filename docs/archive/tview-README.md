# 📺 启视 · TVIEW Launcher

把 Ubuntu 变成一台由遥控器/手柄操控的电视盒子 —— 开机即用，支持 Linux 应用 + 安卓应用（Waydroid）

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Ubuntu%2024.04-orange.svg)
![Version](https://img.shields.io/badge/version-v0.1-green.svg)


## ✨ 特性

- 🎮 遥控器 + 手柄操控：方向键、确认键、返回键全映射，长按返回键强制回到主界面
- 📦 应用一键安装：内置当贝市场、F-Droid、Google Play、Kodi、VLC，下载即装
- ⚡ 节能模式：默认关闭，用户可手动开启，开启后自动关闭 Ubuntu 桌面，退出时自动恢复
- 🔧 高度可定制：自定义壁纸、桌面列数（2~6列）、自定义 Linux 应用
- 🌐 完整网络控制：WiFi 切换、固定 IP、代理设置
- 🛡️ 钩子命令：进入/退出电视模式时自动执行自定义 Shell 命令（如启动/停止 Docker 容器）
- ⏰ 电视盒子标配：定时关机、屏保、日期时间显示
- 📋 日志导出：一键导出日志，方便反馈问题


## 🚀 快速开始

### 安装
bash <(curl -s https://raw.githubusercontent.com/你的用户名/tview-launcher/main/install.sh)

### 卸载
sudo /opt/tview/uninstall.sh


## 🕹️ 操作指南

| 按键 | 功能 |
|------|------|
| 方向键 | 移动焦点 |
| OK键 | 启动 / 确认 |
| 返回键（长按 3 秒） | 强制回到主界面 |
| 主页键 | 回到主界面 |
| 音量键 | 控制音量 |
| 电源键（长按） | 关机/重启菜单 |

支持游戏手柄：Xbox、PS、Nintendo 手柄即插即用。


## 📸 截图

（待补充）


## ⚙️ 系统要求

- Ubuntu 24.04 LTS（Wayland 会话）
- Intel 核显 / AMD APU
- USB 2.4G 遥控器 / 蓝牙遥控器 / 游戏手柄
- 8GB 内存（推荐）


## 📚 文档

- 用户手册：/docs/USER_GUIDE.md
- 产品需求文档：/docs/PRD.md
- AI 编程指令集：/docs/AI_PROMPT.md


## 🧩 技术栈

| 组件 | 说明 |
|------|------|
| Python 3.10 + PyQt5 | 前端界面 |
| Waydroid | 安卓容器 |
| Cage | 轻量级 Wayland 合成器 |
| evdev | 遥控器/手柄输入 |
| Systemd | 进程管理 |
| nmcli | 网络管理 |


## 🗺️ 未来路线图

| 版本 | 目标 |
|------|------|
| v0.1 | 启动器应用（当前阶段） |
| v1.0 | 稳定版启动器 + 完整设置面板 |
| v2.0 | 独立 Wayland 桌面会话 |
| v3.0 | 基于 Ubuntu 的魔改发行版 ISO |


## 🤝 贡献

欢迎提交 Issue 和 Pull Request！


## 📄 许可证

MIT License


## ❤️ 致谢

灵感来源于把闲置电脑变成电视盒子的无数折腾者。