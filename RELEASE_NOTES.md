# 启视·TVIEW v0.1.0-beta.1 发布说明

> 把一台 Ubuntu 电脑变成电视盒子。
> 仓库：<https://github.com/chimingxu126/tview> · 许可：MIT

## 这是什么

TVIEW 是运行在 Ubuntu 上的电视盒子启动器：PyQt5 全屏界面 + Waydroid 安卓容器 + keyd 遥控器系统驱动。普通 x86 电脑接上电视和遥控器，就是一台能装安卓 TV 应用的盒子。

**核心亮点**：
- 安卓 TV 生态全兼容——ARM-only 应用（当贝市场、酷安等）通过 libhoudini 转译层正常安装运行
- 遥控器即插即用——非标 2.4G 遥控器键位在系统层标准化，返回/主页/菜单/音量在安卓应用内原生生效
- 开机直达——免密登录自动进启动器，老人小孩都会用

## 功能

- 🏠 全屏电视界面：应用网格（列数可调）、顶部状态栏（时间/日期/网络/安卓状态）、底部导航
- 📱 Waydroid 安卓容器：应用列表秒开、启动/停止控制、APK 安装（U 盘/本地/市场）
- 🎮 遥控器：keyd 系统级键位标准化 + 自定义按键映射（录制模式）
- 🎨 5 套内置主题（极光/科技/星空/明亮/极简）+ 自定义配色壁纸，对比度自动保障
- 🌐 中/英文界面一键切换
- 📦 内置市场：F-Droid（自动下载）、当贝市场（引导获取）
- ⚡ 开机自启、开机免密、看门狗、日志导出、电源/重启菜单
- 🔒 退出盒子自动锁屏（默认，需密码进桌面；设置可改免密直退）

界面效果见 [README.md](README.md) 截图（极光/科技蓝双主题）。

## 安装

```bash
git clone https://github.com/chimingxu126/tview.git
cd tview
sudo bash scripts/install.sh
```

安装器 11 步全自动（系统层 → Waydroid → 转译层引导 → keyd → 部署 → 应用 → 音量 → 免密 → 自启 → 验收），幂等可重跑。系统要求：Ubuntu 24.04/26.04 桌面版（x86_64）、4GB 内存以上、安装时联网（安卓镜像约 2.6GB）。

两件第三方资产（版权原因不随仓库分发，安装器会引导）：**libhoudini 转译层**（waydroid_script 或本地资产）与**当贝市场 APK**（官网下载放 `assets/apks/`）。

详细步骤见 [README.md](README.md)。

## 验证

- 真机（i7-7代/HD630/8GB）：当贝/酷安/Foni 等 ARM 应用装+跑通；遥控器全键位实测；冒烟测试 30/30
- CI：GitHub Actions 自动构建 + 冒烟测试 + Release 发布，全绿
- 发行二进制：`tview`（PyInstaller 单文件，本 Release 附件）

## 已知问题

- 长按返回 3 秒在安卓应用聚焦时不生效（安卓返回键本身可用，简化处理）
- Waydroid "启动"按钮在 GNOME 桌面环境可能失败，盒子模式（开机免密）下正常
- F-Droid 走 GitHub 直链，国内网络不稳时用内置 APK 或 U 盘安装兜底
- 无 GPU 的虚拟机里安卓桌面可能起不来（真实硬件无此问题）
- IR 红外遥控器暂不支持（需 lirc 扩展）

## 路线图（下一版）

- **L2 kiosk 安全模式**：TVIEW 专用会话（cage 合成器），遥控器唯一入口，退出盒子回登录界面，物理输入无法绕过 TVIEW（方案见 DEVELOPMENT.md §10）
- 应用分类、CEC、蓝牙配对、代理、中文输入法

## 反馈

GitHub Issues，附 `~/.config/tview/logs/tview.log`。
