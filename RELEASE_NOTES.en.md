# QiShi TVIEW v0.2.0-beta.1 Release Notes

> Turn an Ubuntu PC into a TV box.
> Repo: <https://github.com/chimingxu126/tview> · License: MIT

## What is this

TVIEW is a TV-box launcher for Ubuntu: PyQt5 fullscreen UI + Waydroid Android container + keyd remote driver. Plug a TV and a remote into an ordinary x86 PC and it becomes a box that runs Android TV apps.

**v0.2 headline: L2 TV box mode (kiosk)**
- Boots straight into a **dedicated TVIEW session** (labwc compositor, no desktop environment) — the remote is the only entry point, physical keyboard/mouse cannot bypass TVIEW; exiting returns to the login screen (password required)
- Built-in **VNC remote**: auto-starts in box mode; view & control from any LAN VNC client
- **Runtime mode switchable in Settings**: TV box mode / Desktop mode (GNOME + auto-start) / Normal login

## Features

- 🏠 Fullscreen TV UI: app grid (adjustable columns), top status bar, bottom navigation
- 📱 Waydroid Android container: ARM-only apps (Dangbei/CoolApk…) via libhoudini translation; instant app list, APK install (USB/local/store)
- 🐧 Native Linux apps (Kodi/Firefox…) in the same grid as Android apps
- 🎮 Remote: keyd system-level key normalization (Back/Home/Volume work natively inside Android) + custom key mapping
- 🔒 Security: TV box mode (default) + exit-locks-screen (desktop mode default) + optional VNC password
- 🎨 5 built-in themes + custom colors/wallpaper, contrast auto-guaranteed
- 🌐 Chinese & English UI, one-click switch
- 📦 Built-in stores: F-Droid (auto-download), Dangbei Market (guided)
- ⚡ Auto-start (optional at install, default on), watchdog, log export, power menu

Screenshots in [README.md](README.md).

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

- Real hardware (i7-7th/HD630/8GB): Dangbei/CoolApk/Foni ARM apps installed & ran; full remote keymap verified; window switching (wlrctl focus) verified; smoke tests 30/30
- Clean VM (Ubuntu 26.04): installer full flow + box-mode config + VNC service/LAN handshake + mode switching (box/desktop/normal) verified
- CI: GitHub Actions build + smoke test + Release publishing, all green
- Binary: `tview` (PyInstaller single file, attached to this Release)

## Known issues

- Long-press Back 3s does not work while an Android app is focused (Android Back works; simplified)
- Waydroid "Start" button may fail in GNOME desktop sessions; fine in box mode
- F-Droid uses a GitHub direct link; on unstable CN networks use the bundled APK or USB install
- Android UI may not start in GPU-less VMs (real hardware unaffected)
- IR remotes not yet supported (needs lirc)
- VNC remote input unavailable in GPU-less VMs (headless lacks virtual-pointer protocol); fine on real hardware

## Feedback

GitHub Issues; attach `~/.config/tview/logs/tview.log`.
