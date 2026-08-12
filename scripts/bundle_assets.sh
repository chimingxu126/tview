#!/bin/bash
# ============================================================
# 兼容层资产打包脚本 —— 从当前已验证环境提取，供安装器离线使用
# 用法: bash scripts/bundle_assets.sh [--with-images]
#   --with-images  同时打包 system.img/vendor.img（约 3GB，离线重装用）
# 产物: assets/ 目录 + assets/manifest.json
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

ASSETS="assets"
mkdir -p "$ASSETS/houdini/system/lib64" "$ASSETS/apks"
MANIFEST="$ASSETS/manifest.json"

echo "===== [1/4] 提取 ARM 兼容层（libhoudini）====="
SRC_OVERLAY="/var/lib/waydroid/overlay/system/lib64"
if [ -f "$SRC_OVERLAY/libhoudini.so" ]; then
    cp -v "$SRC_OVERLAY/libhoudini.so" "$ASSETS/houdini/system/lib64/"
    if [ -d "$SRC_OVERLAY/arm64" ]; then
        cp -rv "$SRC_OVERLAY/arm64" "$ASSETS/houdini/system/lib64/"
    fi
else
    echo "!! 未找到 $SRC_OVERLAY/libhoudini.so，兼容层缺失！"
    echo "   请确认 Waydroid 环境已安装 libhoudini（waydroid_script -o libhoudini）"
    exit 1
fi

echo "===== [2/4] 收集内置 APK ====="
APK_SRC=(
    "$HOME/下载/dangbeimarket.apk:apks/dangbeimarket.apk"
    "$HOME/下载/飯太硬.apk:apks/foni.apk"
)
for pair in "${APK_SRC[@]}"; do
    src="${pair%%:*}"; dst="${pair##*:}"
    if [ -f "$src" ]; then
        cp -v "$src" "$ASSETS/$dst"
    else
        echo "-- 跳过（不存在）: $src"
    fi
done

echo "===== [3/4] 可选：打包本地镜像 ====="
if [ "${1:-}" = "--with-images" ]; then
    mkdir -p "$ASSETS/images"
    for img in system.img vendor.img; do
        [ -f "/var/lib/waydroid/images/$img" ] && cp -v "/var/lib/waydroid/images/$img" "$ASSETS/images/"
    done
else
    echo "-- 未指定 --with-images，跳过镜像（安装器将在线 init）"
fi

echo "===== [4/4] 生成清单 ====="
cat > "$MANIFEST" <<EOF
{
  "generated": "$(date -Is)",
  "houdini": {
    "source": "$SRC_OVERLAY",
    "files": [$(find "$ASSETS/houdini" -type f | sed 's|^|"|; s|$|",|' | tr -d '\n' | sed 's/,$//')]
  },
  "apks": [$(find "$ASSETS/apks" -type f -name "*.apk" -exec sha256sum {} + | awk '{print "{\"file\":\""$2"\",\"sha256\":\""$1"\"},"}' | tr -d '\n' | sed 's/,$//')]
}
EOF
echo "清单已生成: $MANIFEST"
echo
echo "完成。assets/ 目录即可随安装器分发（离线安装兼容层+当贝市场）。"
du -sh "$ASSETS"
