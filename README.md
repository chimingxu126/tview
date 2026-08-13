# 启视·TVIEW

**把一台 Ubuntu 电脑变成电视盒子。**

TVIEW 是一个运行在 Ubuntu 上的电视盒子启动器：接上电视和遥控器，普通 x86 电脑（或迷你主机）就变成一台能装安卓 TV 应用的盒子——当贝市场、酷安、B 站 TV 版……想装什么装什么。

[![Build](https://github.com/chimingxu126/tview/actions/workflows/build.yml/badge.svg)](https://github.com/chimingxu126/tview/actions)

**核心亮点**：
- 📱 **安卓 TV 生态**：当贝市场/酷安等 ARM-only 应用直接装直接跑（libhoudini 转译层）
- 🎮 **遥控器即插即用**：返回/主页/音量在安卓应用内原生生效（keyd 系统级键位标准化）
- 🔒 **安全盒子模式**：labwc 专用会话，遥控器唯一入口，物理键盘/鼠标无法绕过
- 🖥️ **显示器唤醒**：桌面模式下打开显示器（电视）自动进入 TVIEW

> [English](README.en.md) · 中文

![极光主题主界面](docs/screenshots/main-aurora.png)

## 能做什么

- **🏠 全屏电视界面**：应用网格 + 顶部状态栏（时间/日期/网络）+ 底部导航，遥控器完全操作（设置页同时支持键鼠点击，底部有返回/退出按钮）
- **📱 安卓 TV 生态**：基于 Waydroid 跑安卓系统，ARM-only 应用（当贝/酷安等）通过 libhoudini 转译层运行
- **🎮 遥控器原生支持**：2.4G 遥控器即插即用——返回/主页/菜单/音量在安卓应用里原生生效，方向键/OK 操作界面；按键可自定义映射
- **🐧 原生 Linux 应用**：设置里手动添加任意 Linux 应用（Kodi、Firefox 等），与安卓应用同网格、遥控器同操作
- **🎨 多主题界面**：极光/科技蓝/暗星空/明亮等 5 套内置主题 + 自定义配色壁纸，切换即时生效（自动保障对比度）
- **📦 软件安装中心**：当贝市场 / F-Droid / U 盘安装三合一
- **💾 U 盘自动挂载到安卓**：设置开关，安卓内直接访问 U 盘文件
- **↩️ 应用退出返回 TVIEW**：退出应用自动回主界面（设置可关）
- **🌐 中英文界面**，设置里一键切换
- **⚡ 省心集成**：开机自启（安装时可选）、看门狗（崩溃自动恢复）、日志导出、重启/关机菜单
- **🔒 安全**：详见下方"安全模型"
- **🖥️ 显示器唤醒 TVIEW**：桌面模式下检测到显示器开启 → 自动进入 TVIEW（设置里可开关/选特定显示器）

![科技蓝主题主界面](docs/screenshots/main-tech.png)

## 安全模型（两种运行模式，设置里可切换）

| 模式 | 开机行为 | 安全性 |
|---|---|---|
| **盒子模式**（默认，推荐） | 免密直达 TVIEW **专用会话**（labwc 合成器，无桌面环境） | 遥控器是唯一入口，物理键盘/鼠标无法绕过 TVIEW；退出盒子回到登录界面（要密码）；**局域网 VNC 远程可看可操作** |
| **桌面模式** | 免密进 GNOME 桌面 + 自启 TVIEW | 退出盒子默认锁屏（需密码进桌面），设置里可改免密直退 |

- 盒子模式 = 电视盒子本来的样子：开机就是 TVIEW，谁碰都是一台"只有遥控器能用"的盒子
- 远程排障：盒子模式用 **VNC**（Win/Mac 任意 VNC 客户端连 `盒子IP:5900`）；SSH 常开兜底；要完整桌面就登录界面选 GNOME

## 工作原理（30 秒看懂）

```
Ubuntu ──► TVIEW 启动器（PyQt5 全屏 UI）
   │
   ├─► Waydroid 安卓容器：跑 TV 应用
   │      └─ libhoudini 转译层：x86 机器跑 ARM 应用
   │
   ├─► keyd 系统驱动：遥控器键位标准化
   │      （非标遥控器码 → 标准 Back/Home/Menu/音量键）
   │
   └─► labwc 合成器（盒子模式）：TVIEW 独占会话 + VNC 远程
```

- **遥控器**：大多数 2.4G 遥控器的返回/主页/音量走"媒体键"通道，普通系统不认识。TVIEW 用 keyd 在系统层把它们标准化成标准键码——所以安卓应用里按返回就是返回，按音量就是音量。
- **安卓应用**：Waydroid 容器内运行完整安卓系统；ARM-only 的 TV 应用由 libhoudini 自动转译（这就是为什么当贝市场这种"只出 ARM 版"的应用也能装能跑）。

## 硬件要求

| 项目 | 要求 |
|---|---|
| 电脑 | x86_64，4GB 内存以上（建议 8GB），建议 i3/同等或以上 |
| 系统 | Ubuntu 24.04 / 26.04 桌面版（全新安装） |
| 电视/显示器 | HDMI 接入 |
| 遥控器 | USB 2.4G 遥控器（推荐）或 USB 键盘 |
| 网络 | 安装时需联网（下载安卓镜像约 2.6GB） |

## 安装

### 1. 准备系统

全新安装 Ubuntu 桌面版（24.04 或 26.04），完成系统初始设置（用户名/密码）。

### 2. 获取 TVIEW

```bash
git clone https://github.com/chimingxu126/tview.git
cd tview
```

### 3. 一键安装

```bash
sudo bash scripts/install.sh
```

安装器自动完成 11 步（约 15-30 分钟，视网络），**交互询问两项**（直接回车用默认）：
- 开机自动启动 TVIEW？`[Y/n]`（默认开）
- 运行模式：盒子模式？`[Y/n]`（默认盒子模式；n=桌面模式）

11 步：系统层（binder/input 组/sudoers 白名单/udev）→ 安装 Waydroid（自动匹配 Ubuntu 版本）→ 初始化安卓镜像（约 2.6GB）→ ARM 转译层（libhoudini 引导）→ keyd 遥控器驱动 → 部署 TVIEW + 会话/自启 → 内置应用 → 安卓音量初始化 → 开机免密 → 自启检查 → 验收。

> 安装器幂等，任何一步失败修复后重跑即可。非交互环境（如自动化脚本）加 `--no-ask` 全部用默认值；`--desktop-mode` 强制桌面模式；`--no-autostart` 跳过开机自启。

### 4. 两件需要手动获取的事（版权原因）

安装器会引导你完成：

**① ARM 转译层 libhoudini**（不装则安卓 ARM 应用无法运行）——二选一：
- 在线：`bash -c "$(curl -s https://raw.githubusercontent.com/casualsnek/waydroid_script/main/install.sh)"`，菜单选 libhoudini
- 离线：从已有 TVIEW 机器拷贝 `assets/houdini/` 目录，然后 `sudo bash scripts/install.sh --local-assets .`

**② 当贝市场 APK**：到 <https://www.dangbei.com/> 下载，放到 `assets/apks/dangbeimarket.apk`，重跑安装器自动安装。

### 5. 完成

重启电脑 → 自动进入 TVIEW（盒子模式）或桌面（桌面模式）。搞定。

## 遥控器按键

| 按键 | 功能 |
|---|---|
| 方向键 / OK | 移动焦点 / 确认 |
| 返回 | 返回 / 退出应用 |
| 主页 | 回主页（TVIEW 或安卓桌面） |
| 菜单 | 应用菜单 |
| 音量 +/− | 系统音量（安卓内也生效） |
| 设置键 | 打开设置 |
| 长按返回 3 秒 | 从安卓应用回 TVIEW |

## 遥控器交互（安卓 TV 范式）

- **主界面**：上下键在顶部导航行（设置/软件安装/退出盒子/电源）与应用网格之间移动；
  返回键把焦点切到导航行；OK 激活焦点项
- **设置页**（全屏）：左右键切换分类/改值，上下键移动选项，OK 确认/进入，
  返回键逐级退出（子页→分类→主界面）；安全选项下方直接标注风险

## 显示器唤醒 TVIEW

桌面模式（远程编程/离开后回来）下，打开显示器自动进入 TVIEW——适合"平时远程用电脑、到家开电视就看盒子"的场景。

- 设置 → **显示器唤醒 TVIEW**（默认开）：开关关闭则完全禁用
- 唤醒方式：**任意显示器**开启即唤醒；或**仅特定显示器**（勾选列表，如只认电视）
- 检测走 Linux DRM 层，**HDMI/DP/VGA/DVI/USB-C 等所有接口通用**；显示器列表显示接口 + 厂商型号
- 安全：不绕过任何认证；**开启本功能会自动禁用系统闲置锁屏**（否则锁屏会挡住 TVIEW）；
  盒子模式 TVIEW 常驻，无需此功能
- 提示：勾选"特定显示器"时，该显示器需处于开启状态才会出现在列表中

## VNC 远程（盒子模式）

盒子模式下 TVIEW 自动启动 VNC 服务（`盒子IP:5900`）。用任意 VNC 客户端（RealVNC/TigerVNC 等）连接即可远程查看/操作 TVIEW 界面——适合盒子放在客厅、你在书房远程管理。

- 密码：默认无（局域网信任环境）；如需密码，编辑 `~/.config/tview/config.yaml` 的 `vnc_password` 后重启 TVIEW
- 注意：VNC 仅覆盖 TVIEW 界面；系统级操作请走 SSH

## 从源码运行 / 构建

```bash
sudo apt install -y python3-pyqt5 python3-evdev python3-yaml
python3 main.py --mock    # 模拟模式（无硬件可试）
python3 main.py --prod    # 生产模式

# 打包单文件二进制
pip install pyinstaller
pyinstaller --clean -y tview.spec    # 产物 dist/tview
```

## 已知问题

- 长按返回 3 秒在安卓应用聚焦时不生效（安卓返回键本身可用，简化处理）
- Waydroid "启动"按钮在 GNOME 桌面环境可能失败，盒子模式（开机免密）下正常
- F-Droid 走 GitHub 直链，国内网络不稳时用内置 APK 或 U 盘安装兜底
- 无 GPU 的虚拟机里安卓桌面可能起不来（真实硬件无此问题）
- IR 红外遥控器暂不支持（需要 lirc 扩展）
- VNC 远程输入在无 GPU 虚拟机（headless 缺虚拟指针协议）里不可用，真实硬件正常

## 路线图

- 应用分类、CEC 遥控、蓝牙配对、代理设置、中文输入法
- TVIEW 发行版（Cubic 定制 ISO）

## 许可

MIT，见 [LICENSE](LICENSE)。仓库不包含 libhoudini 与商业 APK 等第三方专有资产，请按安装引导自行获取并遵守其各自许可。

## 开发文档

架构设计与真机实测记录见 [DEVELOPMENT.md](DEVELOPMENT.md)。
