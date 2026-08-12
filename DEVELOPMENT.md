# 启视·TVIEW 开发文档（v0.1 修订版）

> 本文档是 PRD/AI_PROMPT 的**修订版**，替代原文档中已被评审否决的设计。
> 评审结论来源：2026-08-07 架构评审 + 2026-08-08 真机验证（当贝市场/酷安/Foni 在 x86_64 Waydroid 上装+跑成功）。
> 本文档只写**定稿结论**，不保留被否掉的方案，避免后续开发被旧文档误导。

---

## 0. 验证结论（真机实测，2026-08-08）

| 项 | 结果 | 影响 |
|---|---|---|
| Waydroid 1.6.2 + GApps 镜像（x86_64） | ✅ 正常 | 基础成立 |
| ARM-only APK（当贝市场/酷安/Foni）装+跑 | ✅ 正常 | **死穴解除**：ARM 转译有效 |
| **ARM 转译来源** | ⚠️ **后装**：libhoudini.so + arm64/ 在 `/var/lib/waydroid/overlay/`（修改层），**官方镜像不带** | 安装器必须自带兼容层，否则清空重装后 ARM 应用全灭 |
| 当贝市场在 Waydroid 内运行 | ✅ 正常 | 生态层通 |
| 遥控器操作 Waydroid 应用 | ✅ 之前已实测 | 输入通道通 |
| 原生 Ubuntu 界面（密码框等）遥控器操作 | ❓ 未测（设计上不依赖） | autologin + NOPASSWD 白名单绕开 |
| 硬件 | i7 7代 / HD630 / 8GB | 性能充足，**2GB 内存约束作废** |

## 1. 关键架构修正（相对原文档）

### 1.1 输入流：grab/ungrab 状态机（原方案"全程独占"是错的）
- **状态 A（HOME）**：tview 前台，grab 遥控器，evdev 事件只喂 tview
- **状态 B（APP）**：启动安卓应用 → **ungrab**，按键自然流向 Waydroid 窗口（安卓应用内用安卓自己的导航）
- 返回：**长按返回键 3 秒** → 重新 grab + 隐藏 Waydroid 窗口，回状态 A
- 必须处理设备热插拔（掉线重连后重新 grab，失败重试）
- 主页键语义：安卓内按主页 → 回安卓桌面（不是 tview）；长按返回 → 回 tview

### 1.2 窗口共存：前台独占模型（Cage 不做同屏共存）
- tview 与 Waydroid 永远只有一个可见
- 切换机制：窗口 minimize/activate（wlrctl / xdg-activation），**Cage 实测不灵就换 labwc**（成本极低）
- 这是 v0.1 最大技术风险点，阶段 1 必须单独验证

### 1.3 系统集成：自定义 Wayland 会话 + GDM autologin（放弃 kill GDM）
- `/usr/share/wayland-sessions/tview.desktop` → `cage -- /opt/tview/main.py --prod`
- GDM AutomaticLogin 直进盒子模式
- "退出盒子" = `loginctl terminate-session` 回 GDM 登录界面
- **盒子模式内不允许出现 sudo/polkit 密码弹窗**：install.sh 配 `/etc/sudoers.d/tview` NOPASSWD 白名单（reboot、shutdown、systemctl、nmcli、waydroid、apt 特定操作），不给全量 sudo
- 排障兜底：SSH 常开（默认），tview 设置留"退出到桌面"入口

### 1.4 明确修正的技术错误（原文档）
| 原文档 | 修正 |
|---|---|
| xrandr 调分辨率 | Wayland 下用 **wlr-randr**（Cage 是 wlroots 系） |
| Google Play 从 APKMirror 下载 | **砍掉**。改为：检测镜像是否带 GApps（`pm list packages | grep vending`），无则提示重装 GApps 镜像；替代品 **Aurora Store** |
| ping 8.8.8.8 探测网络 | 默认 **223.5.5.5**（阿里 DNS），可配置 |
| Python 3.10 | **直接用系统 Python（3.12+，本机 3.14）**，不折腾 PPA |
| 内存 ≤2GB | 作废。实测 8GB 机器，无此约束 |
| 当贝市场 URL 硬编码 | 下载前 **HEAD 探测**，失败给提示；APK 优先走**安装包内置资产**（离线） |
| 看门狗/安全模式定义冲突 | 统一：启动失败 2 次 → 第 3 次安全模式（不启 Waydroid、最小界面+日志导出）；运行中看门狗 3 次重启失败 → 停止 Waydroid 回主界面弹提示，**不是退出盒子** |

## 2. 兼容层与安装器（本轮新增，最高优先级）

### 2.1 事实
- 官方 `waydroid init -s GAPPS` 拉取的镜像 **不含** ARM 转译
- 当前环境转译 = waydroid_script 安装的 libhoudini（`/var/lib/waydroid/overlay/system/lib64/libhoudini.so` + `arm64/` 目录 + prop 的 native.bridge 配置）
- 清空重装后必须重装兼容层，否则当贝市场等 ARM-only APK 装不上

### 2.2 安装器流程（v0.1）
```
1. 系统层：binder 模块（/etc/modules-load.d/waydroid.conf）、input 组、
   NOPASSWD sudoers、udev（USB 唤醒）、GDM autologin + tview.desktop
2. waydroid：apt 安装 → init（优先本地镜像包，备选在线 GAPPS）
3. 兼容层：复制内置 houdini 资产（libhoudini.so + arm64/）到 overlay + 写 prop
   （离线主路径；waydroid_script 在线为备选）
4. 设置 waydroid.background_start=true（开机后台预启动容器）
5. 启动会话 → waydroid app install 内置 APK（当贝市场等）
6. 验收：libhoudini 存在 + 当贝在应用列表 + launch 成功 + 遥控器可操作
```
- **本地镜像包**：安装器支持从内置 system.img/vendor.img 离线 init，不依赖网络
- **APK 资产**：当贝市场（已验证）、电视家（推荐）、F-Droid，全部内置
- 安装器自身也要**可重复执行**（幂等），失败可重跑

## 3. 阶段划分

| 阶段 | 内容 | 验收 |
|---|---|---|
| **阶段 1（当前）** | 最小原型：启动器网格 + 遥控器 grab/ungrab + Waydroid 应用管理 + mock 模式 | 消除 B 层风险（输入流/窗口切换），架构验证 |
| v0.1 | 完整启动器 + 设置面板 + 安装器 + 清空重装验收 | 干净环境一键复现全部功能 |
| v1.0 | 稳定版：CEC、蓝牙配对、应用分类、代理、中文输入法 | 产品可用 |
| v2.0 | 深度定制 wlroots 合成器（labwc 起步） | "类桌面环境" |
| v3.0 | 发行版（Cubic 定制 ISO） | 可分发 |

## 4. 阶段 1 范围（MVP，砍掉一切干扰项）

### 必须做
- 全屏启动器：深色背景 #1a1a2e、顶部状态栏（日期/时间/网络）、应用网格（默认 3 列 2~6 可调）、底部"设置/应用下载"入口
- 遥控器：evdev 检测 + grab/ungrab 状态机 + 长按返回 3 秒回主页 + 热插拔重连
- Waydroid 管理：`app list`（含图标）/ `app launch` / `app install`
- Linux 应用：`~/.config/tview/linux_apps.json` 手动添加
- 市场（简版）：当贝市场（内置 APK 资产 + URL 探测备选）、F-Droid
- mock 模式：模拟应用列表/图标/安装/命令日志，纯开发环境可全流程跑通
- 日志：`~/.config/tview/logs/tview.log`（10MB 滚动）+ crash.log
- 看门狗（简版）：30s 检测 waydroid status，3 次失败重启会话，3 次重启失败回主界面
- 设置（简版）：列数、壁纸（可选）、退出盒子、重启/关机、日志导出

### 明确不做（推迟）
- 代理、儿童模式、应用分类、中文虚拟键盘、定时关机、屏保、USB 唤醒 UI、WiFi 管理 UI（这些 v0.1/v1.0）
- Google Play 下载、APKMirror

## 5. 模块设计

```
main.py                 # 入口，--prod/--mock，异常捕获写 crash.log
tview/config.py         # YAML 配置（~/.config/tview/config.yaml）
tview/logging_setup.py  # 日志初始化（滚动 10MB + crash.log）
tview/remote.py         # evdev 遥控器：设备检测/grab/ungrab/按键映射/长按
tview/waydroid.py       # waydroid 命令封装（list/launch/install/status）
tview/apps.py           # 统一应用模型（安卓+Linux → 应用卡片）
tview/ui/main_window.py # 主窗口：状态栏 + 网格 + 底部按钮 + 设置/市场
tview/ui/vkeyboard.py   # 虚拟键盘（阶段1：字母数字）
scripts/bundle_assets.sh # 兼容层资产 + APK 打包（从当前环境提取）
scripts/install.sh      # v0.1 安装器（阶段 1 先做骨架）
```

## 6. 关键依赖
- PyQt5（系统包 python3-pyqt5）、evdev、pyyaml
- waydroid、cage、wlr-randr、nmcli
- 注意：Python 3.14 下优先 apt 装 python3-evdev，其次 pip（--break-system-packages）

## 7. 验收标准（阶段 1）
1. `python3 main.py --mock` 无报错，网格显示模拟应用，方向键/确认/返回可用
2. 真机：遥控器在 HOME 态可操作网格，启动安卓应用后按键流入 Waydroid，长按返回 3 秒回主页
3. 当贝市场 APK 安装成功且出现在网格
4. 看门狗在 waydroid 假死后能恢复（mock 可模拟）
5. 代码模块与本文档一致，日志完整

## 8. 待真机验证（用户回家后）
- 当贝市场内下载电视家/B站TV → 装 → 播
- 原生 sudo 密码框遥控器是否可用（记录即可，不影响设计）
- Cage 下窗口切换机制（wlrctl）实测；不灵换 labwc

---

## 9. 真机实测记录（2026-08-08 晚，用户在家）

### 9.1 遥控器按键地图（实测，非标准码！）
2.4G 遥控器（USB Composite Device 接收器）拆成多个接口：

| 功能 | keycode | 接口 | 备注 |
|---|---|---|---|
| OK | KEY_ENTER (28) | 键盘 event5 | 标准 |
| 方向 | KEY_UP/DOWN/LEFT/RIGHT | 键盘 event5 | 标准 |
| 菜单 | **KEY_COMPOSE (127)** | 键盘 event5 | 非标准，Android 不映射 |
| 返回 | **KEY_BACK (158)** | Consumer Control event4 | 非标准 |
| 主页 | **KEY_HOMEPAGE (172)** | Consumer Control event4 | 非标准 |
| 音量+/- | KEY_VOLUMEUP/DOWN (115/114) | Consumer Control event4 | 标准 |

**结论**：遥控器模块必须**同时监听全部接口**（不能只开键盘接口，否则音量/返回/主页丢失），且返回/主页/菜单要用真实 keycode（KEY_BACK/KEY_HOMEPAGE/KEY_COMPOSE）。

### 9.2 音量问题真相
- 系统侧链路正常（PipeWire → HDMI sink 100%）
- **“几乎没声音”= 安卓内部音量只有 5/15**（33%）
- 修复：`cmd media_session volume --stream 3 --set 15`（lxc-attach 进容器执行）
- tview 音量键用 `wpctl set-volume @DEFAULT_SINK@ 0.05+/-`（**pactl 未安装，用 wpctl**）
- 待办：安装脚本里加“首次启动把安卓音量拉满”步骤

### 9.3 待办（v0.1）
- Waydroid 菜单键：KEY_COMPOSE 安卓不认，需自定义 keylayout（/system/usr/keylayout）
- 安装器补：安卓音量初始化、waydroid.background_start=true 验证
- Cage 会话下验证音量键能否直达 Waydroid（wlroots 全设备转发，预期可行）
