#!/bin/bash
# 启视·TVIEW 开机免密开关（GDM autologin）
# 用法: sudo tview-autologin.sh on|off|status [session]
#   session 参数: gnome（默认，桌面模式：autologin 进 GNOME + autostart tview）
#                 tview（盒子模式 L2：autologin 直接进 TVIEW kiosk 会话 labwc）
# 说明: 幂等，改前自动备份 /etc/gdm3/custom.conf
CONF=/etc/gdm3/custom.conf
BAK=/etc/gdm3/custom.conf.bak-tview

apply() { # $1=true|false  $2=session
  cp -a "$CONF" "$BAK" 2>/dev/null || true
  python3 - "$1" "$SUDO_USER" "$2" <<'PY'
import re, sys
enable = sys.argv[1] == "true"
user = sys.argv[2] or "chimingxu"
session = sys.argv[3] or "gnome"
path = "/etc/gdm3/custom.conf"
s = open(path, encoding="utf-8").read()
if "[daemon]" not in s:
    s = s.rstrip() + "\n\n[daemon]\n"

def set_kv(s, key, val):
    m = re.search(r"\[daemon\](.*?)(?=\n\[|\Z)", s, re.S)
    body = m.group(1)
    new = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={val}", body, flags=re.M)
    if new == body:
        new = body.rstrip() + f"\n{key}={val}\n"
    return s[:m.start(1)] + new + s[m.end(1):]

s = set_kv(s, "AutomaticLoginEnable", "true" if enable else "false")
if enable:
    s = set_kv(s, "AutomaticLogin", user)
    s = set_kv(s, "AutomaticLoginSession", session)
else:
    s = re.sub(r"^AutomaticLogin(Enable|Session)?=.*$", "", s, flags=re.M)
s = re.sub(r"\n{3,}", "\n\n", s)  # 压缩多余空行
open(path, "w", encoding="utf-8").write(s)
PY
}

case "$1" in
  on)  apply true "${2:-gnome}";  echo "enabled (session=${2:-gnome})" ;;
  off) apply false; echo "disabled" ;;
  status)
    grep -q "^AutomaticLoginEnable=true" "$CONF" && echo "enabled" || echo "disabled"
    grep -q "^AutomaticLoginSession=tview" "$CONF" && echo "session=tview" || echo "session=gnome" ;;
  *) echo "usage: $0 on|off|status [gnome|tview]"; exit 1 ;;
esac
