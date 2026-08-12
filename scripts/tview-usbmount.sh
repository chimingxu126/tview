#!/bin/bash
# 启视·TVIEW U 盘自动挂载到安卓开关（BETA 0.4）
# 用法: sudo tview-usbmount.sh on|off|status
# 原理: 把宿主 /media（U 盘自动挂载点）bind 进 Waydroid 容器 /media，
#       安卓文件管理器即可访问 U 盘；容器重启生效
# 回退: 手动编辑 /var/lib/waydroid/lxc/waydroid/config 删除 lxc.mount.entry=/media 行
CONF=/var/lib/waydroid/lxc/waydroid/config
LINE="lxc.mount.entry = /media media none bind 0 0"

case "$1" in
  on)
    grep -qF "$LINE" "$CONF" 2>/dev/null || echo "$LINE" >> "$CONF"
    systemctl restart waydroid-container 2>/dev/null || true
    echo "enabled"
    ;;
  off)
    grep -vF "$LINE" "$CONF" > "${CONF}.tmp" 2>/dev/null && mv "${CONF}.tmp" "$CONF"
    systemctl restart waydroid-container 2>/dev/null || true
    echo "disabled"
    ;;
  status)
    grep -qF "$LINE" "$CONF" 2>/dev/null && echo "enabled" || echo "disabled"
    ;;
  *) echo "usage: $0 on|off|status"; exit 1 ;;
esac
