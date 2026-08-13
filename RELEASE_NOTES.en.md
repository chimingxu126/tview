# QiShi TVIEW v0.4.1 Release Notes

> Turn an Ubuntu PC into a TV box.
> Repo: <https://github.com/chimingxu126/tview> · License: MIT

## What is this

TVIEW is a TV-box launcher for Ubuntu: PyQt5 fullscreen UI + Waydroid Android container + keyd remote driver. Plug a TV and a remote into an ordinary x86 PC and it becomes a box that runs Android TV apps.

**BETA 0.4.1: Settings page keyboard & mouse fixes (desktop / remote-desktop scenarios)**
- **Mouse fully works in Settings**: click a category to switch page, click a switch/action row to run it, click an option row to select it — same semantics as the remote OK key; rows/buttons show hover feedback
- **Bottom nav buttons**: "‹ Back" + "✕ Exit Settings" always visible at bottom-right; clickable by mouse and reachable by remote/keyboard (keep pressing Down past the last row)
- **Fixed child-dialog keys being swallowed**: while USB install / app store / keymap dialogs are open, Back/Enter are no longer intercepted by the Settings page (previously Back could not close them)
- **USB install dialog restyled**: dark theme, larger window; lists APKs automatically when a USB stick is inserted

**v0.4 headline: UI overhaul (Android TV paradigm)**
- **Top navigation row** on the main screen (Settings/App Install/Exit box/Power); Back moves focus to the nav row — fully remote-operable
- **Settings rewritten as a fullscreen view**: category rail + option list, no dropdowns; Up/Down move, Left/Right change, OK confirm, Back steps out; security options show risk notes inline
- **App Install center**: Dangbei/F-Droid/USB unified; **USB auto-mount into Android** (switch); **return to TVIEW when apps exit** (switch)
- Fixes: settings could not scroll, language dropdown trapped the remote, display-wake was covered by the screen lock (wake now disables idle lock automatically)

## Features

- 🖥️ **Wake TVIEW on display on** (new in BETA 0.3): auto-enters TVIEW when a display turns on; any/specific displays
- 🏠 **Top navigation** (BETA 0.4): Settings/App Install/Exit box/Power at the top; Back goes straight to it
- 📄 **Fullscreen Settings** (BETA 0.4 + 0.4.1): categorized + remote interaction + risk notes; mouse-clickable, bottom Back/Exit buttons
- 💾 **USB auto-mount into Android** + **return to TVIEW on app exit** (BETA 0.4)
- 🏠 Fullscreen TV UI: app grid (adjustable columns), top status bar, bottom navigation
- 📱 Waydroid Android container: ARM-only apps (Dangbei/CoolApk…) via libhoudini translation; instant app list, APK install (USB/local/store)
- 🐧 Native Linux apps (Kodi/Firefox…) in the same grid as Android apps
- 🎮 Remote: keyd system-level key normalization (Back/Home/Volume work natively inside Android) + custom key mapping
- 🔒 Security: TV box mode (default, labwc kiosk session, remote is the only entry) + exit-locks-screen (desktop mode default) + optional VNC password
- 🎨 5 built-in themes + custom colors/wallpaper, contrast auto-guaranteed
- 🌐 Chinese & English UI, one-click switch
- 📦 App Install center: F-Droid (auto-download), Dangbei Market (guided), USB install
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

- Dev machine (i7-7th/HD630/8GB): smoke tests 35/35; Settings key/mouse full-path scenarios (button-zone nav, click category, click switch, click exit, click option row) and child-dialog popup/Back-close tests all pass
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
