# QiShi TVIEW v0.3.0-beta.1 Release Notes

> Turn an Ubuntu PC into a TV box.
> Repo: <https://github.com/chimingxu126/tview> · License: MIT

## What is this

TVIEW is a TV-box launcher for Ubuntu: PyQt5 fullscreen UI + Waydroid Android container + keyd remote driver. Plug a TV and a remote into an ordinary x86 PC and it becomes a box that runs Android TV apps.

**v0.3 headline: Wake TVIEW on display on**
- In desktop mode, **turning on a display auto-opens TVIEW** — remote-work all day, come home and turn on the TV to get the box UI directly
- Switchable in Settings (default ON); choose **any display** or **specific displays only** (checklist with connector + vendor/model)
- Detection reads the Linux DRM layer — **all interfaces (HDMI/DP/VGA/DVI/USB-C) work uniformly**; never bypasses authentication; no conflict with L1/L2 security models

## Features

- 🖥️ **Wake TVIEW on display on** (new in BETA 0.3): auto-enters TVIEW when a display turns on; any/specific displays
- 🏠 Fullscreen TV UI: app grid (adjustable columns), top status bar, bottom navigation
- 📱 Waydroid Android container: ARM-only apps (Dangbei/CoolApk…) via libhoudini translation; instant app list, APK install (USB/local/store)
- 🐧 Native Linux apps (Kodi/Firefox…) in the same grid as Android apps
- 🎮 Remote: keyd system-level key normalization (Back/Home/Volume work natively inside Android) + custom key mapping
- 🔒 Security: TV box mode (default, labwc kiosk session, remote is the only entry) + exit-locks-screen (desktop mode default) + optional VNC password
- 🎨 5 built-in themes + custom colors/wallpaper, contrast auto-guaranteed
- 🌐 Chinese & English UI, one-click switch
- 📦 Built-in stores: F-Droid (auto-download), Dangbei Market (guided)
- ⚡ Auto-start (optional at install, default on), watchdog, log export, power menu

## Installation

```bash
git clone https://github.com/chimingxu126/tview.git
cd tview
sudo bash scripts/install.sh
```

11 automatic steps; two interactive questions (Enter = default): **auto-start on boot** (default yes), **TV box mode** (default box mode). Requirements: Ubuntu 24.04/26.04 desktop (x86_64), 4GB+ RAM, internet during install.

Two third-party items (not bundled for copyright reasons; the installer guides you): **libhoudini** translation layer (waydroid_script or local assets) and the **Dangbei Market APK** (download from the official site into `assets/apks/`).

Full steps: [README.md](README.md) / [README.en.md](README.en.md).

## Verification

- Dev machine (i7-7th/HD630/8GB): smoke tests 33/33; wake trigger logic unit-tested (hit/miss/any/disabled); watch background mode starts cleanly
- Clean VM (Ubuntu 26.04): smoke tests 29/29, watch startup OK
- Previously verified: ARM apps (Dangbei/CoolApk/Foni) installed & ran; full remote keymap; labwc window switching; VNC LAN handshake; installer full flow
- CI: GitHub Actions build + smoke test + Release publishing, all green
- Binary: `tview` (PyInstaller single file, attached to this Release)

## Known issues

- When picking "specific displays", the display must be powered on (EDID readable) to appear in the list
- Rare displays that only enter DPMS sleep without any event rely on polling fallback (detected within ~30s)
- Long-press Back 3s does not work while an Android app is focused (Android Back works; simplified)
- Waydroid "Start" button may fail in GNOME desktop sessions; fine in box mode
- F-Droid uses a GitHub direct link; on unstable CN networks use the bundled APK or USB install
- Android UI may not start in GPU-less VMs (real hardware unaffected)
- IR remotes not yet supported (needs lirc)

## Feedback

GitHub Issues; attach `~/.config/tview/logs/tview.log`.
