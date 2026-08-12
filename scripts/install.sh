#!/bin/bash
# ============================================================
# 启视·TVIEW v0.2.0-beta.1 安装器（引导下载版）
#
# 设计原则：
#   1. 不捆绑任何第三方专有资产（libhoudini / 商业 APK），一律引导下载或本地提供
#   2. 幂等：可重复执行，失败可重跑
#   3. 目标：一台干净 Ubuntu 24.04/26.04 跑完本脚本 = 与开发机一致的可运行盒子
#
# 用法: sudo bash install.sh [选项]
#   --local-images      使用 assets/images/ 本地镜像离线 waydroid init（省约 2GB 下载）
#   --local-assets DIR  使用 DIR 下的离线资产（DIR/houdini/ 与 DIR/apks/），跳过引导下载
#   --tview-bin PATH    指定 tview 二进制位置（默认同目录 ./tview）
#   --skip-apps         跳过内置 APK 安装（当贝/F-Droid）
#   --skip-tview        跳过 tview 本体部署（只做系统层 + Waydroid + 兼容层）
#   --no-autostart      不写开机自启（默认写；交互安装时会让用户选择）
#   --desktop-mode      桌面模式（autologin 进 GNOME + 自启）；默认盒子模式（labwc kiosk）
#   --no-ask            不交互询问（全部用默认值）
#
# 依据: DEVELOPMENT.md §2.2 / §9（真机实测）/ §10（L2 kiosk）
# ============================================================
set -uo pipefail
cd "$(dirname "$0")/.."

[ "$(id -u)" = "0" ] || { echo "❌ 请用 sudo 运行: sudo bash scripts/install.sh"; exit 1; }

USER_NAME="${SUDO_USER:-$(whoami)}"
USER_HOME="$(eval echo ~${USER_NAME})"
ASSETS="assets"
LOCAL_ASSETS=""
TVIEW_BIN=""
SKIP_APPS=0
SKIP_TVIEW=0
AUTOSTART_ASK=1
AUTOSTART_SET=1
DESKTOP_MODE=0
STEP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --local-images)  LOCAL_IMAGES=1 ;;
    --local-assets)  shift; LOCAL_ASSETS="$1" ;;
    --tview-bin)     shift; TVIEW_BIN="$1" ;;
    --skip-apps)     SKIP_APPS=1 ;;
    --skip-tview)    SKIP_TVIEW=1 ;;
    --no-autostart)  AUTOSTART_ASK=0; AUTOSTART_SET=0 ;;
    --desktop-mode)  DESKTOP_MODE=1 ;;
    --no-ask)        AUTOSTART_ASK=0 ;;
    *) echo "未知参数: $1（忽略）" ;;
  esac
  shift
done

# 交互询问：是否开机自启（默认开）与运行模式（默认盒子模式）
if [ "${AUTOSTART_ASK}" = "1" ] && [ -t 0 ]; then
  echo
  read -r -p "开机自动启动 TVIEW？[Y/n] " _ans
  case "$_ans" in
    n|N|no) AUTOSTART_SET=0 ;;
    *)      AUTOSTART_SET=1 ;;
  esac
  echo
  read -r -p "运行模式：盒子模式（开机直达 TVIEW，最安全）[Y/n，n=桌面模式] " _ans2
  case "$_ans2" in
    n|N|no) DESKTOP_MODE=1 ;;
    *)      DESKTOP_MODE=0 ;;
  esac
fi

say() { STEP=$((STEP+1)); echo; echo "===== [$STEP/11] $1 ====="; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ 缺少 $1，先: sudo apt install -y $1"; exit 1; }; }

echo "============================================================"
echo " 启视·TVIEW v0.1.0-beta.1 安装器"
echo " 目标用户: ${USER_NAME}   本地资产: ${LOCAL_ASSETS:-无(引导下载)}"
echo "============================================================"

# ---------- 1. 系统层 ----------
say "系统层：binder 模块 / input 组 / sudoers 白名单 / udev"
modprobe binder_linux 2>/dev/null || modprobe binder 2>/dev/null || true
grep -q binder_linux /etc/modules-load.d/waydroid.conf 2>/dev/null || \
  echo "binder_linux" > /etc/modules-load.d/waydroid.conf
grep -q binder /etc/modules-load.d/waydroid.conf 2>/dev/null || \
  echo "binder" >> /etc/modules-load.d/waydroid.conf

usermod -aG input "$USER_NAME" 2>/dev/null || true
usermod -aG waydroid "$USER_NAME" 2>/dev/null || true

# NOPASSWD 白名单：盒子模式禁止密码弹窗，只放行必要命令（不给全量 sudo）
cat > /etc/sudoers.d/tview <<EOF
# 启视·TVIEW 白名单：仅放行盒子模式需要的命令
Cmnd_Alias TVIEW_CMDS = /sbin/reboot, /sbin/shutdown, /bin/systemctl, \
    /usr/bin/systemctl, /usr/bin/nmcli, /usr/bin/waydroid, /usr/bin/apt, \
    /usr/bin/apt-get, /usr/bin/pactl, /usr/bin/wpctl, /usr/local/sbin/tview-usbmount.sh
%sudo ALL=(ALL) NOPASSWD: TVIEW_CMDS
EOF
chmod 440 /etc/sudoers.d/tview
visudo -c -f /etc/sudoers.d/tview >/dev/null 2>&1 && echo "✅ sudoers 白名单" || echo "⚠️ sudoers 语法校验失败，请检查 /etc/sudoers.d/tview"

# udev：遥控器/USB 输入设备归 input 组，普通用户可读
cat > /etc/udev/rules.d/90-tview-input.rules <<'EOF'
# 启视·TVIEW：输入设备归 input 组（遥控器 keyd/tview 可读）
KERNEL=="event*", SUBSYSTEM=="input", GROUP="input", MODE="0660"
EOF
udevadm control --reload-rules 2>/dev/null || true
echo "✅ udev 规则"

# ---------- 2. Waydroid ----------
say "安装 Waydroid"
if ! command -v waydroid >/dev/null 2>&1; then
  need curl
  curl -s --proto '=https' --tlsv1.2 -Sf https://repo.waydro.id/waydroid.gpg \
    -o /usr/share/keyrings/waydroid.gpg || { echo "❌ 下载 waydroid 源失败（需联网）"; exit 1; }
  # 发行版代号动态检测（noble=24.04 / resolute=26.04 / 未来版本自动适配）
  CODENAME=$(lsb_release -cs 2>/dev/null || grep -oP 'UBUNTU_CODENAME=\K.*' /etc/os-release)
  [ -n "$CODENAME" ] || CODENAME="noble"
  echo "deb [signed-by=/usr/share/keyrings/waydroid.gpg] https://repo.waydro.id/ ${CODENAME} main" \
    > /etc/apt/sources.list.d/waydroid.list
  echo ">>> 使用 ${CODENAME} 源安装 waydroid"
  apt-get update -qq && apt-get install -y waydroid python3-pyqt5 python3-evdev python3-yaml wlrctl labwc wayvnc || {
    echo "❌ waydroid 安装失败（看上面依赖错误；若为 python3-gbinder 冲突，确认源代号是否匹配系统版本）"
    exit 1; }
else
  apt-get install -y python3-pyqt5 python3-evdev python3-yaml wlrctl labwc wayvnc 2>/dev/null || true
fi
if command -v waydroid >/dev/null 2>&1; then
  echo "✅ waydroid: $(waydroid --version 2>/dev/null | head -1 || echo installed)"
else
  echo "❌ waydroid 仍未就绪（PATH 中找不到），请检查安装输出"
  exit 1
fi

# ---------- 3. 初始化镜像 ----------
say "初始化 Waydroid 镜像（GApps）"
if [ "${LOCAL_IMAGES:-0}" = "1" ] && [ -f "$ASSETS/images/system.img" ]; then
  echo ">>> 使用本地镜像离线 init"
  mkdir -p /var/lib/waydroid/images
  cp -v "$ASSETS/images/system.img" "$ASSETS/images/vendor.img" /var/lib/waydroid/images/ 2>/dev/null
fi
if [ ! -f /var/lib/waydroid/images/system.img ]; then
  echo ">>> 在线下载 GAPPS 镜像（约 2GB，耐心等待；有本地镜像可加 --local-images）"
  if ! waydroid init -s GAPPS; then
    echo
    echo "⚠️ waydroid init 失败（多为网络问题，GAPPS 镜像在国内不可达）。可选："
    echo "  1. 挂代理后重跑本脚本（幂等）"
    echo "  2. 加 --local-images 使用本地镜像包"
    echo "  3. 稍后手动: sudo waydroid init -s GAPPS"
    echo
  fi
else
  waydroid init -s GAPPS 2>/dev/null || echo ">>> 镜像已存在，跳过 init"
fi
# 开机后台预启动容器（避免首次点应用等半天）
waydroid prop set persist.waydroid.background_start true 2>/dev/null || \
  sed -i 's/waydroid.background_start=false/waydroid.background_start=true/' /var/lib/waydroid/waydroid.prop 2>/dev/null || true

# ---------- 4. ARM 兼容层（libhoudini）----------
say "ARM 兼容层（libhoudini）"
DEST=/var/lib/waydroid/overlay/system/lib64
if [ -n "$LOCAL_ASSETS" ] && [ -f "$LOCAL_ASSETS/houdini/system/lib64/libhoudini.so" ]; then
  mkdir -p "$DEST"
  cp -v "$LOCAL_ASSETS/houdini/system/lib64/libhoudini.so" "$DEST/"
  [ -d "$LOCAL_ASSETS/houdini/system/lib64/arm64" ] && cp -rv "$LOCAL_ASSETS/houdini/system/lib64/arm64" "$DEST/"
elif [ -f "$ASSETS/houdini/system/lib64/libhoudini.so" ]; then
  # 仓库自带的离线资产（用户自行放入，.gitignore 排除，不入 repo）
  mkdir -p "$DEST"
  cp -v "$ASSETS/houdini/system/lib64/libhoudini.so" "$DEST/"
  [ -d "$ASSETS/houdini/system/lib64/arm64" ] && cp -rv "$ASSETS/houdini/system/lib64/arm64" "$DEST/"
else
  echo ">>> 未找到离线 houdini 资产，跳过自动下载（版权原因不代下，需用户引导获取）"
  if [ ! -f "$DEST/libhoudini.so" ]; then
    echo
    echo "⚠️ 兼容层未安装。ARM-only 应用（当贝/酷安等）将无法运行。请二选一："
    echo "  A. 在线（推荐）：运行 waydroid_script 官方脚本，菜单选 1 (libhoudini)"
    echo "     bash -c \"\$(curl -s https://raw.githubusercontent.com/casualsnek/waydroid_script/main/install.sh)\""
    echo "  B. 离线：从已有 TVIEW 机器拷贝 assets/houdini/ 目录放到本仓库，然后重跑:"
    echo "     sudo bash scripts/install.sh --local-assets ."
    echo
  fi
fi
if [ -f "$DEST/libhoudini.so" ]; then
  cat >> /var/lib/waydroid/waydroid.prop <<'EOF'
ro.dalvik.vm.native.bridge=libhoudini.so
ro.enable.native.bridge.exec=1
ro.dalvik.vm.isa.arm=x86
ro.dalvik.vm.isa.arm64=x86_64
EOF
  echo "✅ 兼容层在位 + prop 已配置"
else
  echo "⚠️ 兼容层缺失（不影响本安装器其余步骤，但 ARM 应用不可用）"
fi

# ---------- 5. keyd（遥控器系统驱动，标准件）----------
say "keyd 遥控器驱动"
if ! command -v keyd >/dev/null 2>&1; then
  apt-get install -y keyd || { echo "❌ keyd 安装失败"; exit 1; }
fi
# 实测键位映射（2026-08-08 真机验证）：非标键标准化成系统/安卓都认的标准键
cat > /etc/keyd/default.conf <<'EOF'
# 启视·TVIEW 遥控器驱动（keyd，系统级标准件）
# 依据实测 keycode：USB Composite Device 2.4G 遥控器
#  键盘接口: OK=28 方向=103/108/105/106 菜单=127 设置=14(退格) 信号源=111
#  CC 接口:  返回=158 主页=172 音量+=115 音量-=114
# 标准化后：tview 走 Qt 事件路径（自动不 grab），安卓收到标准 BACK/HOME/MENU 原生处理
# 回退: sudo systemctl stop keyd && sudo rm /etc/keyd/default.conf
[ids]
*

[main]
158 = back          # 返回键 → 标准 Back（安卓 BACK / Qt Key_Back）
172 = home          # 主页键 → 标准 Home
127 = menu          # 菜单键 → 标准 Menu
14  = backspace     # 设置键 → 退格（tview 解释为打开设置）
111 = delete        # 信号源 → Delete
115 = volumeup      # 音量+ → 标准媒体键（系统/安卓原生处理）
114 = volumedown    # 音量- → 标准媒体键
113 = mute          # 静音 → 标准媒体键
EOF
systemctl enable keyd && systemctl restart keyd
systemctl is-active keyd >/dev/null && echo "✅ keyd 运行中" || echo "⚠️ keyd 未运行，检查: systemctl status keyd"

# ---------- 6. 部署 tview 本体 ----------
if [ "${SKIP_TVIEW}" = "1" ]; then
  say "跳过 tview 本体部署（--skip-tview）"
else
  say "部署 tview 到 /opt/tview"
  BIN=""
  if [ -n "$TVIEW_BIN" ] && [ -x "$TVIEW_BIN" ]; then BIN="$TVIEW_BIN"
  elif [ -f "./tview" ] && [ -x "./tview" ]; then BIN="./tview"
  elif [ -f "./dist/tview" ] && [ -x "./dist/tview" ]; then BIN="./dist/tview"
  elif [ -f "./tview-bin" ] && [ -x "./tview-bin" ]; then BIN="./tview-bin"
  fi
  if [ -z "$BIN" ]; then
    echo ">>> 未找到本地二进制，尝试从 GitHub Release 下载最新版..."
    need curl
    VER=$(curl -s https://api.github.com/repos/chimingxu126/tview/releases/latest | grep -oP '"tag_name":\s*"\K[^"]+' | head -1)
    if [ -n "$VER" ]; then
      # 注意：仓库内有 tview/ 包目录，下载到 tview-bin 避免冲突
      curl -L -o ./tview-bin "https://github.com/chimingxu126/tview/releases/download/${VER}/tview" && chmod +x ./tview-bin && BIN="./tview-bin"
    fi
  fi
  if [ -z "$BIN" ]; then
    echo "⚠️ 未找到 tview 二进制。请从 GitHub Releases 下载后放本目录，或: sudo bash scripts/install.sh --tview-bin /path/to/tview"
  else
    mkdir -p /opt/tview/assets
    # 重装时旧实例可能在运行，先停掉（否则 cp 报“文本文件忙”）
    pkill -f '/opt/tview/tview' 2>/dev/null || true
    sleep 1
    if ! cp -v "$BIN" /opt/tview/tview; then
      echo "❌ 复制二进制失败: $BIN -> /opt/tview/tview"
    else
      chmod +x /opt/tview/tview
      # 资产：只拷贝无版权风险的（壁纸/UI/清单）；apks/ 与 houdini/ 不随仓库分发
      cp -rv assets/wallpapers /opt/tview/assets/ 2>/dev/null || true
      cp -rv assets/ui /opt/tview/assets/ 2>/dev/null || true
      cp -v assets/manifest.json /opt/tview/assets/ 2>/dev/null || true
      # 用户自备的 APK 资产（可选，跳过下载时存在）
      if [ -d "assets/apks" ] && ls assets/apks/*.apk >/dev/null 2>&1; then
        cp -rv assets/apks /opt/tview/assets/ 2>/dev/null || true
      fi
      cat > /opt/tview/start.sh <<'SH'
#!/bin/bash
cd "$(dirname "$0")"
exec ./tview --prod
SH
      chmod +x /opt/tview/start.sh
      # TVIEW kiosk 会话（L2）：GDM 登录界面可选“启视·TVIEW（盒子模式）”，
      # labwc 合成器，tview 退出即会话结束回登录界面
      mkdir -p /usr/share/wayland-sessions
      install -m 644 /dev/stdin /usr/share/wayland-sessions/tview.desktop <<'EOF'
[Desktop Entry]
Name=启视·TVIEW（盒子模式）
Name[en]=TVIEW (Box Mode)
Comment=TV box kiosk session (labwc)
Exec=/usr/bin/labwc -S /opt/tview/tview --prod
Type=Application
EOF
      echo "✅ kiosk 会话已注册（/usr/share/wayland-sessions/tview.desktop）"
      # 图标与应用菜单入口（GNOME 应用列表可见，随时可启动）
      cp -v assets/ui/tview.png /opt/tview/assets/ui/ 2>/dev/null || true
      APPS_DIR="$USER_HOME/.local/share/applications"
      mkdir -p "$APPS_DIR"
      cat > "$APPS_DIR/tview.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=启视·TVIEW
Name[en]=TVIEW
Comment=TV box launcher
Exec=/opt/tview/tview --prod
Icon=/opt/tview/assets/ui/tview.png
Terminal=false
Categories=Utility;
EOF
      chown -R "$USER_NAME:$USER_NAME" "$APPS_DIR" 2>/dev/null || true
      # 开机自启（autostart，默认开；--no-autostart 或交互选 n 时跳过）
      if [ "${AUTOSTART_SET}" = "1" ]; then
        mkdir -p "$USER_HOME/.config/autostart"
        cat > "$USER_HOME/.config/autostart/tview.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=启视·TVIEW
Comment=TV box launcher
Exec=/opt/tview/tview --prod
Icon=/opt/tview/assets/ui/tview.png
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
        chown -R "$USER_NAME:$USER_NAME" "$USER_HOME/.config/autostart" 2>/dev/null || true
        # 显示器唤醒监听（桌面模式后台常驻；labwc 盒子会话不读 autostart，天然不冲突）
        cat > "$USER_HOME/.config/autostart/tview-watch.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TVIEW Display Wake
Comment=Wake TVIEW when display turns on
Exec=/opt/tview/tview --watch
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
        chown -R "$USER_NAME:$USER_NAME" "$USER_HOME/.config/autostart" 2>/dev/null || true
        echo "✅ 开机自启已配置"
      else
        echo "ℹ️ 已按选择跳过开机自启（可稍后: 设置 → 开机自动启动）"
      fi
      update-desktop-database "$APPS_DIR" 2>/dev/null || true
      if [ -x /opt/tview/tview ]; then
        echo "✅ tview 部署完成: /opt/tview/tview（应用菜单入口已注册）"
      else
        echo "❌ /opt/tview/tview 不可执行，部署失败"
      fi
    fi
  fi
fi

# ---------- 7. 内置 APK（引导下载，不入仓库）----------
if [ "${SKIP_APPS}" = "1" ]; then
  say "跳过内置 APK 安装（--skip-apps）"
else
  say "内置 APK（当贝市场 / F-Droid）"
  APK_DIR="assets/apks"
  [ -n "$LOCAL_ASSETS" ] && APK_DIR="$LOCAL_ASSETS/apks"
  mkdir -p "$APK_DIR"
  need curl
  # F-Droid：GitHub 官方 Release 直链（已实测可用）
  if [ ! -f "$APK_DIR/fdroid.apk" ]; then
    echo ">>> 下载 F-Droid 1.18.0（GitHub 官方直链）"
    curl -L --connect-timeout 10 -o "$APK_DIR/fdroid.apk.part" \
      https://github.com/f-droid/fdroidclient/releases/download/1.18.0/F-Droid.apk \
      && mv "$APK_DIR/fdroid.apk.part" "$APK_DIR/fdroid.apk" \
      || rm -f "$APK_DIR/fdroid.apk.part"
  fi
  # 当贝市场：官网无稳定直链，引导用户下载
  if [ ! -f "$APK_DIR/dangbeimarket.apk" ]; then
    echo
    echo ">>> 当贝市场 APK 需要手动获取（版权原因不内置不代下）:"
    echo "    1. 浏览器打开 https://www.dangbei.com/ （当贝官网）"
    echo "    2. 下载当贝市场 TV 版 APK，保存为: $(pwd)/$APK_DIR/dangbeimarket.apk"
    echo "    3. 重跑本脚本即可自动安装（幂等，跳过已下载项）"
    echo
  fi
  # 安装 APK
  systemctl start waydroid-container 2>/dev/null || true
  for apk in "$APK_DIR"/*.apk; do
    [ -f "$apk" ] || continue
    echo ">>> 安装 $(basename "$apk")"
    sudo -u "$USER_NAME" waydroid app install "$apk" 2>/dev/null \
      && echo "    ✅ 安装成功" \
      || echo "    ⚠️ 安装失败/容器未就绪（可稍后重跑本脚本）"
  done
fi

# ---------- 8. 安卓音量拉满（“几乎没声音”真相：安卓内部 5/15）----------
say "安卓媒体音量初始化"
systemctl start waydroid-container 2>/dev/null || true
sleep 2
if lxc-info -n waydroid >/dev/null 2>&1; then
  lxc-attach -n waydroid -- cmd media_session volume --stream 3 --set 15 2>/dev/null \
    && echo "✅ 安卓音量已拉满 15/15" \
    || echo "⚠️ 容器未就绪，稍后手动执行: sudo lxc-attach -n waydroid -- cmd media_session volume --stream 3 --set 15"
else
  echo "⚠️ 容器未运行，跳过（tview 首次启动时会自动拉起容器）"
fi

# ---------- 9. 开机免密（GDM autologin）----------
say "开机免密（可选，默认开启）"
install -m 755 scripts/tview-autologin.sh /usr/local/sbin/tview-autologin.sh 2>/dev/null || \
  install -m 755 /usr/local/sbin/tview-autologin.sh /usr/local/sbin/tview-autologin.sh 2>/dev/null || true
install -m 755 scripts/tview-usbmount.sh /usr/local/sbin/tview-usbmount.sh 2>/dev/null || true
if [ -x /usr/local/sbin/tview-autologin.sh ]; then
  cat > /etc/sudoers.d/tview-autologin <<EOF
# tview 开机免密开关脚本白名单
${USER_NAME} ALL=(ALL) NOPASSWD: /usr/local/sbin/tview-autologin.sh
EOF
  chmod 440 /etc/sudoers.d/tview-autologin
  # 盒子模式 L2：autologin 直接进 TVIEW kiosk 会话（labwc）；
  # 桌面模式（排障/远程）：autologin 进 GNOME + autostart tview，可设 DESKTOP_MODE=1 切换
  AUTOLOGIN_SESSION="tview"
  [ "${DESKTOP_MODE:-0}" = "1" ] && AUTOLOGIN_SESSION="gnome"
  /usr/local/sbin/tview-autologin.sh on "$AUTOLOGIN_SESSION" >/dev/null 2>&1 \
    && echo "✅ 开机免密已开启（autologin 会话=${AUTOLOGIN_SESSION}）" \
    || echo "⚠️ 免密开启失败（手动: sudo /usr/local/sbin/tview-autologin.sh on ${AUTOLOGIN_SESSION}）"
fi

# ---------- 10. 重启后自启路径 ----------
say "自启链路检查"
AUTOSTART="$USER_HOME/.config/autostart/tview.desktop"
if [ -f "$AUTOSTART" ]; then
  echo "✅ autostart: $AUTOSTART"
  grep Exec "$AUTOSTART"
else
  echo "⚠️ autostart 文件缺失（--skip-tview 时正常；否则检查上一步）"
fi

# ---------- 11. 验收 ----------
say "验收"
PASS=0; FAIL=0
check() { # $1=描述 $2=条件
  if eval "$2"; then echo "✅ $1"; PASS=$((PASS+1)); else echo "❌ $1"; FAIL=$((FAIL+1)); fi
}
check "binder 模块" "grep -q binder /etc/modules-load.d/waydroid.conf"
check "waydroid 已装" "command -v waydroid >/dev/null 2>&1"
check "keyd 运行中" "systemctl is-active keyd >/dev/null 2>&1"
check "兼容层在位" "[ -f /var/lib/waydroid/overlay/system/lib64/libhoudini.so ]"
check "sudoers 白名单" "[ -f /etc/sudoers.d/tview ]"
check "autologin 脚本" "[ -x /usr/local/sbin/tview-autologin.sh ]"
check "tview 二进制" "[ -x /opt/tview/tview ]"
check "autostart 文件" "[ -f '$AUTOSTART' ]"
echo
echo "============================================================"
echo " 验收: ${PASS} 通过 / ${FAIL} 失败"
if [ "$FAIL" -gt 0 ]; then
  echo " 有失败项，修复后重跑本脚本（幂等，安全）"
else
  echo " 🎉 安装完成！重启后自动进入 TVIEW。"
  echo " 排障: SSH(22) 常开；tview 设置里有日志导出"
fi
echo "============================================================"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
