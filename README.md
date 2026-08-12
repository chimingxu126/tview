# 启视·TVIEW

把 Ubuntu 变成电视盒子（TV box）的启动器。基于 Waydroid 跑安卓 TV 生态（当贝市场、酷安等），keyd 做遥控器系统级驱动，PyQt5 全屏启动器 UI。

> **BETA 状态**：v0.1.0-beta.1。功能可用，安装器待在干净机器上验收（见 [CHANGELOG](CHANGELOG.md)）。

## 功能

- 🏠 全屏启动器：应用网格（3~6 列）、顶部状态栏（时间/日期/网络/Waydroid 状态）、底部胶囊导航
- 📱 Waydroid 安卓容器：应用列表（自动读取 .desktop 缓存，秒开）、启动/停止、APK 安装（含 U 盘安装）
- 🎮 遥控器：keyd 系统级键位标准化（非标 2.4G 遥控器实测），返回/主页/音量在安卓应用内原生可用；支持自定义按键映射（学习模式）
- 🎨 主题系统：5 套内置主题 + 自定义配色/壁纸，WCAG 对比度自动保障
- 🌐 多语言：中文 / English
- 📦 应用市场：当贝市场（APK 资产引导）、F-Droid（GitHub 直链）
- ⚡ 其他：开机自启、开机免密（GDM autologin）、看门狗、日志导出、电源/重启菜单

## 安装（干净 Ubuntu 24.04）

```bash
git clone https://github.com/chimingxu126/tview.git
cd tview
sudo bash scripts/install.sh          # 完整安装
# 可选参数：
#   --local-images    用本地镜像离线 waydroid init（省约 2GB 下载）
#   --local-assets DIR 使用 DIR 下的离线资产（houdini/ 与 apks/）
#   --skip-apps       跳过内置 APK
#   --skip-tview      只做系统层 + Waydroid
```

安装器会引导你完成两件**需要手动获取**的第三方资产（版权原因不随仓库分发）：

1. **ARM 兼容层 libhoudini**（跑 ARM-only 安卓应用必需）：
   - 在线：运行 waydroid_script 官方脚本，菜单选 libhoudini
     ```bash
     bash -c "$(curl -s https://raw.githubusercontent.com/casualsnek/waydroid_script/main/install.sh)"
     ```
   - 离线：从已有 TVIEW 机器拷贝 `assets/houdini/` 到仓库目录，重跑 `install.sh --local-assets .`
2. **当贝市场 APK**：官网 <https://www.dangbei.com/> 下载后放到 `assets/apks/dangbeimarket.apk`，重跑安装器

安装完成后重启，自动进入 TVIEW。排障兜底：SSH(22) 常开。

## 从源码运行（开发）

```bash
sudo apt install -y python3-pyqt5 python3-evdev python3-yaml
pip install --break-system-packages pyinstaller   # 仅打包需要
python3 main.py --mock    # 模拟模式，无硬件可跑
python3 main.py --prod    # 生产模式
```

## 构建二进制

```bash
pyinstaller --clean -y tview.spec   # 产物 dist/tview（单文件，不含第三方资产）
```

## 硬件实测环境

- B250M-D3V / i7 7代 / HD630 / 8GB / Ubuntu（内核 6+，binder 模块）
- Waydroid 1.6.2 + GApps 镜像（x86_64）+ libhoudini（ARM 转译）
- 2.4G USB 遥控器（USB Composite Device，键盘 + Consumer Control 双接口）

详细架构与实测记录见 [DEVELOPMENT.md](DEVELOPMENT.md)。

## 已知问题（v0.1.0-beta.1）

- 长按返回 3 秒回主页：HOME 态可用，安卓应用聚焦时不生效（安卓返回键本身可用，简化处理）
- Waydroid "启动"按钮在 GNOME 桌面环境可能失败（session 需 Wayland 显示环境），盒子模式（autologin）下正常
- F-Droid 下载走 GitHub 直链，国内网络不稳时用内置 APK 或 U 盘安装兜底
- PyQt5 无 `Qt.Key_Power`，电源键未纳入按键映射

## 许可

MIT，见 [LICENSE](LICENSE)。注意：仓库**不包含** libhoudini 与商业 APK 等第三方专有资产，请按上文引导自行获取并遵守其各自许可。
