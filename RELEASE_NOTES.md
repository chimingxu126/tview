# 启视·TVIEW v0.2.0-beta.1 发布说明

> 把一台 Ubuntu 电脑变成电视盒子。
> 仓库：<https://github.com/chimingxu126/tview> · 许可：MIT

## 这是什么

TVIEW 是运行在 Ubuntu 上的电视盒子启动器：PyQt5 全屏界面 + Waydroid 安卓容器 + keyd 遥控器系统驱动。普通 x86 电脑接上电视和遥控器，就是一台能装安卓 TV 应用的盒子。

**v0.2 核心升级：L2 盒子模式（kiosk）**
- 开机直达 TVIEW **专用会话**（labwc 合成器，无桌面环境）——遥控器是唯一入口，物理键盘/鼠标无法绕过，退出盒子回登录界面（要密码）
- 内置 **VNC 远程**：盒子模式下自动启动，局域网任意 VNC 客户端可看可操作
- **运行模式可在设置里切换**：盒子模式 / 桌面模式（GNOME + 自启）/ 正常登录

## 功能

- 🏠 全屏电视界面：应用网格（列数可调）、顶部状态栏、底部导航
- 📱 Waydroid 安卓容器：ARM-only 应用（当贝/酷安等）经 libhoudini 转译运行；应用列表秒开、APK 安装（U 盘/本地/市场）
- 🐧 原生 Linux 应用（Kodi/Firefox 等）与安卓同网格启动
- 🎮 遥控器：keyd 系统级键位标准化（返回/主页/音量在安卓内原生生效）+ 自定义按键映射
- 🔒 安全：盒子模式（默认）+ 退出锁屏（桌面模式默认）+ VNC 密码可选
- 🎨 5 套内置主题 + 自定义配色壁纸，对比度自动保障
- 🌐 中/英文界面一键切换
- 📦 内置市场：F-Droid（自动下载）、当贝市场（引导获取）
- ⚡ 开机自启（安装时可选，默认开）、看门狗、日志导出、电源菜单

界面效果见 [README.md](README.md) 截图。

## 安装

```bash
git clone https://github.com/chimingxu126/tview.git
cd tview
sudo bash scripts/install.sh
```

安装器 11 步全自动，交互询问两项（回车用默认）：**是否开机自启**（默认开）、**运行模式**（默认盒子模式）。系统要求：Ubuntu 24.04/26.04 桌面版（x86_64）、4GB 内存以上、安装时联网。

两件第三方资产（版权原因不随仓库分发，安装器会引导）：**libhoudini 转译层**（waydroid_script 或本地资产）与**当贝市场 APK**（官网下载放 `assets/apks/`）。

详细步骤见 [README.md](README.md) / [README.en.md](README.en.md)。

## 验证

- 真机（i7-7代/HD630/8GB）：当贝/酷安/Foni 等 ARM 应用装+跑通；遥控器全键位实测；窗口切换（wlrctl focus）实测；冒烟测试 30/30
- 干净机 VM（Ubuntu 26.04）：安装器全流程 + 盒子模式配置 + VNC 服务/局域网握手 + 模式切换（盒子/桌面/正常）验证通过
- CI：GitHub Actions 自动构建 + 冒烟测试 + Release 发布，全绿
- 发行二进制：`tview`（PyInstaller 单文件，本 Release 附件）

## 已知问题

- 长按返回 3 秒在安卓应用聚焦时不生效（安卓返回键本身可用，简化处理）
- Waydroid "启动"按钮在 GNOME 桌面环境可能失败，盒子模式（开机免密）下正常
- F-Droid 走 GitHub 直链，国内网络不稳时用内置 APK 或 U 盘安装兜底
- 无 GPU 的虚拟机里安卓桌面可能起不来（真实硬件无此问题）
- IR 红外遥控器暂不支持（需 lirc 扩展）
- VNC 远程输入在无 GPU 虚拟机（headless 缺虚拟指针协议）里不可用，真实硬件正常

## 反馈

GitHub Issues，附 `~/.config/tview/logs/tview.log`。
