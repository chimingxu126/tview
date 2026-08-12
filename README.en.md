# QiShi TVIEW

**Turn an Ubuntu PC into a TV box.**

TVIEW is a TV-box launcher for Ubuntu: plug a TV and a remote control into an ordinary x86 PC (or mini PC) and it becomes a box that runs Android TV apps — Dangbei Market, CoolApk, Bilibili TV… whatever you want.

[![Build](https://github.com/chimingxu126/tview/actions/workflows/build.yml/badge.svg)](https://github.com/chimingxu126/tview/actions)

**Highlights**:
- 📱 **Android TV ecosystem**: ARM-only apps (Dangbei/CoolApk…) install and run directly (libhoudini translation)
- 🎮 **Remote works out of the box**: Back/Home/Volume work natively inside Android apps (keyd system-level normalization)
- 🔒 **Secure TV box mode**: dedicated labwc session — the remote is the only entry point; physical keyboard/mouse cannot bypass it
- 🖥️ **Wake on display**: in desktop mode, turning on a display (TV) auto-opens TVIEW

> [中文](README.md) · English

![Aurora theme main screen](docs/screenshots/main-aurora.png)

## Features

- **🏠 Fullscreen TV UI**: app grid + top status bar (clock/date/network) + bottom navigation, fully remote-controlled
- **📱 Android TV ecosystem**: full Android via Waydroid; ARM-only apps (Dangbei, CoolApk…) run through the libhoudini translation layer
- **🎮 Remote control out of the box**: 2.4G remotes work instantly — Back/Home/Menu/Volume work natively inside Android apps; directional pad/OK navigate the UI; keys are remappable
- **🐧 Native Linux apps**: add any Linux app (Kodi, Firefox…) from Settings; it joins the same grid and remote navigation as Android apps
- **🎨 Multiple themes**: 5 built-in themes (Aurora/Tech/Space/Bright/Minimal) + custom colors & wallpaper, applied instantly (WCAG contrast auto-guaranteed)
- **📦 App Install center**: Dangbei Market / F-Droid / USB install in one place
- **💾 Auto-mount USB into Android**: Settings switch; USB drives accessible inside Android
- **↩️ Return to TVIEW when apps exit**: auto back to the main screen (switchable)
- **🌐 Chinese & English UI**, switchable in Settings
- **⚡ Integration**: auto-start (optional at install), watchdog (crash recovery), log export, reboot/power menu
- **🔒 Security**: see "Security model" below
- **🖥️ Wake TVIEW on display on**: in desktop mode, turning on a display auto-opens TVIEW (switchable in Settings / specific-display option)

![Tech blue theme main screen](docs/screenshots/main-tech.png)

## Security model (two modes, switchable in Settings)

| Mode | On boot | Security |
|---|---|---|
| **TV box mode** (default, recommended) | Passwordless boot straight into a **dedicated TVIEW session** (labwc compositor, no desktop environment) | The remote is the ONLY entry point — physical keyboard/mouse cannot bypass TVIEW; exiting returns to the login screen (password required); **LAN VNC remote view & control included** |
| **Desktop mode** | Passwordless GNOME desktop + TVIEW auto-start | Exiting TVIEW locks the screen by default (password to enter desktop); can be set to password-free in Settings |

- TV box mode is what a TV box should be: boots into TVIEW, and anyone touching it gets a box that only responds to the remote.
- Remote troubleshooting: **VNC** in box mode (connect any VNC client to `box-IP:5900`); SSH always on as fallback; pick GNOME at the login screen for the full desktop.

## How it works (30 seconds)

```
Ubuntu ──► TVIEW launcher (PyQt5 fullscreen UI)
   │
   ├─► Waydroid Android container: runs TV apps
   │      └─ libhoudini translation: ARM apps on x86
   │
   ├─► keyd system driver: remote key normalization
   │      (non-standard remote codes → standard Back/Home/Menu/Volume)
   │
   └─► labwc compositor (box mode): TVIEW-only session + VNC
```

- **Remote control**: most 2.4G remotes send Back/Home/Volume over the "media key" channel, which normal systems ignore. TVIEW uses keyd to normalize them at the system level, so Back is Back and Volume is Volume inside Android apps.
- **Android apps**: Waydroid runs a full Android system in a container; ARM-only TV apps are translated automatically by libhoudini (that's why "ARM-only" stores like Dangbei Market install and run fine).

## Hardware requirements

| Item | Requirement |
|---|---|
| PC | x86_64, 4GB+ RAM (8GB recommended), i3-class or better |
| OS | Ubuntu 24.04 / 26.04 desktop (fresh install) |
| TV/display | HDMI input |
| Remote | USB 2.4G remote (recommended) or USB keyboard |
| Network | Internet required during install (~2.6GB Android image) |

## Installation

### 1. Prepare the system

Fresh-install Ubuntu desktop (24.04 or 26.04) and finish initial setup (username/password).

### 2. Get TVIEW

```bash
git clone https://github.com/chimingxu126/tview.git
cd tview
```

### 3. One-shot installer

```bash
sudo bash scripts/install.sh
```

The installer runs 11 automatic steps (about 15-30 min depending on network), asking **two interactive questions** (press Enter for defaults):
- Start TVIEW automatically on boot? `[Y/n]` (default: yes)
- TV box mode? `[Y/n]` (default: box mode; n = desktop mode)

The 11 steps: system layer (binder/input group/sudoers whitelist/udev) → install Waydroid (auto-detects your Ubuntu version) → init Android image (~2.6GB) → ARM translation (libhoudini guided) → keyd remote driver → deploy TVIEW + session/auto-start → bundled apps → Android volume init → passwordless boot → auto-start check → acceptance.

> Idempotent: fix any failed step and re-run. Non-interactive environments: add `--no-ask` for all defaults, `--desktop-mode` to force desktop mode, `--no-autostart` to skip auto-start.

### 4. Two manual items (copyright reasons)

The installer guides you through:

**① ARM translation libhoudini** (required for Android ARM apps) — pick one:
- Online: `bash -c "$(curl -s https://raw.githubusercontent.com/casualsnek/waydroid_script/main/install.sh)"`, choose libhoudini in the menu
- Offline: copy `assets/houdini/` from an existing TVIEW machine, then `sudo bash scripts/install.sh --local-assets .`

**② Dangbei Market APK**: download from <https://www.dangbei.com/>, put it at `assets/apks/dangbeimarket.apk`, re-run the installer.

### 5. Done

Reboot → you land in TVIEW (box mode) or the desktop (desktop mode).

## Remote keys

| Key | Action |
|---|---|
| D-pad / OK | Move focus / confirm |
| Back | Back / exit app |
| Home | Home (TVIEW or Android home) |
| Menu | App menu |
| Vol +/− | System volume (works inside Android) |
| Settings key | Open Settings |
| Long-press Back 3s | Return from Android app to TVIEW |

## Remote interaction (Android TV paradigm)

- **Main screen**: Up/Down move focus between the top nav row (Settings/App Install/Exit box/Power) and the app grid; Back moves focus to the nav row; OK activates the focused item
- **Settings** (fullscreen): Left/Right switch category or change value, Up/Down move options, OK confirm/enter, Back steps out level by level (sub-page → category → main); security options show risk notes below

## VNC remote (box mode)

In box mode TVIEW starts a VNC server automatically (`box-IP:5900`). Connect with any VNC client (RealVNC/TigerVNC…) to view and control the TVIEW UI remotely.

- Password: none by default (trusted LAN); to set one, edit `vnc_password` in `~/.config/tview/config.yaml` and restart TVIEW.
- Note: VNC covers the TVIEW interface only; use SSH for system-level tasks.

## Wake TVIEW on display on

In desktop mode (after remote work / when you come back), turning on a display auto-enters TVIEW — ideal for "use the PC remotely during the day, come home and turn on the TV for the box".

- Settings → **Wake TVIEW on display on** (default ON); turning it off fully disables the feature
- Wake modes: **any display** turns on → wake, or **specific displays only** (checklist, e.g. only the TV)
- Detection reads the Linux DRM layer — **all interfaces (HDMI/DP/VGA/DVI/USB-C) work uniformly**; the list shows connector + vendor/model
- Security: never bypasses authentication; **enabling this feature also disables the system idle screen lock** (otherwise the lock would cover TVIEW); box mode keeps TVIEW resident and needs no such feature
- Note: when picking "specific displays", the display must be powered on to appear in the list

## Run from source / build

```bash
sudo apt install -y python3-pyqt5 python3-evdev python3-yaml
python3 main.py --mock    # mock mode (no hardware needed)
python3 main.py --prod    # production mode

# Build single-file binary
pip install pyinstaller
pyinstaller --clean -y tview.spec    # output: dist/tview
```

## Known issues

- Long-press Back 3s does not work while an Android app is focused (Android Back works; simplified handling)
- The Waydroid "Start" button may fail in a GNOME desktop session; works fine in box mode (passwordless boot)
- F-Droid downloads use a GitHub direct link; on unstable CN networks use the bundled APK or USB install
- Android UI may not start in GPU-less VMs (real hardware unaffected)
- IR remotes not yet supported (needs lirc)
- VNC remote input unavailable in GPU-less VMs (headless lacks the virtual-pointer protocol); fine on real hardware

## Roadmap

- App categories, CEC, Bluetooth pairing, proxy settings, Chinese IME
- TVIEW distro (Cubic custom ISO)

## License

MIT, see [LICENSE](LICENSE). The repo ships no third-party proprietary assets (libhoudini, commercial APKs); obtain them via the installer guidance and respect their respective licenses.

## Development

Architecture and real-hardware test records: [DEVELOPMENT.md](DEVELOPMENT.md).
