# Changelog (English)

## [0.4.0-beta.1] - 2026-08-12

BETA 0.4: **UI overhaul (Android TV paradigm) + interaction fixes**.

### UI rework (remote-friendly; fixes "settings stuck / cannot scroll / hard to control")
- **Main-screen navigation moved to the top**: Settings / App Install / Exit box / Power now sit in a top nav row (bottom dock removed); the Back key moves focus to the nav row (Android TV launcher feel); Up/Down move between nav row and app grid
- **Settings rewritten as a fullscreen view** (long-dialog removed): left category rail + right option list (Display/Input/Apps/System/Security/About); all remote-friendly rows (option rows change value with Left/Right, switch rows toggle with OK, action rows open with OK); Up/Down move, Left/Right switch/change, OK confirm, Back steps out level by level; no more dropdowns
- **Risks documented in the UI**: security-related options show risk notes right below them
- "App Store" renamed **"App Install"** (Dangbei/F-Droid/USB unified; USB install entry merged in)

### New features
- **Auto-mount USB into Android** (Settings switch, default off): binds /media into the Waydroid container so Android file managers can access USB drives; sudoers whitelist + tview-usbmount.sh (idempotent)
- **Return to TVIEW when apps exit** (Settings switch, default on): Linux app process exit returns to the main screen; Android apps returning to the Android home (container foreground polling) auto-return to TVIEW
- **Display-wake linkage**: enabling wake also disables the GNOME idle screen lock (otherwise the lock covers TVIEW — fixes "turned on the display and saw the lock screen")

### Fixes
- Settings dialog could not scroll (plain QDialog, no scroll area) → fullscreen page has no such issue
- Language/theme dropdowns trapped the remote (QComboBox popup vs. direction keys) → replaced with option rows (Left/Right to change)

### Verified
- Dev machine: smoke tests 35/35 (nav model/settings view/new features)
- Clean VM (Ubuntu 26.04): smoke tests 29/29, settings view starts fine

### Known issues
- Android "return to TVIEW" relies on container foreground polling (5s granularity, 20-min cap)
- USB mount requires a Waydroid restart to take effect (switch prompts)
- Legacy SettingsDialog kept for compatibility but no longer used (fullscreen view is used)

## [0.3.0-beta.1] - 2026-08-12

BETA 0.3: **Wake TVIEW on display on** — in desktop mode, TVIEW opens automatically when a display turns on.

### Added
- **Wake TVIEW on display on** (Settings → Wake TVIEW on display on, default ON):
  - Master switch; off fully disables the feature
  - Two wake modes: **any display** turns on → wake, or **specific displays only** (checklist)
  - Display detection reads the Linux DRM layer (`/sys/class/drm`) — **interface-agnostic**: HDMI/DP/VGA/DVI/USB-C all detected uniformly
  - Detection: udev DRM event listener + status polling fallback (dpms Off→On / disconnected→connected both count as "turned on")
  - Display list shows connector + vendor/model (EDID parsed); checked items saved to config
- **Background watch mode** `tview --watch`: auto-started in desktop mode (tview-watch.desktop), headless; skips launch if TVIEW is already running; box mode (labwc) doesn't read autostart, so no conflict
- Security compatible: never bypasses authentication (TVIEW started while locked becomes visible after unlock); L1/L2 security models unchanged

### Verified
- Dev machine: smoke tests 33/33; watch startup + trigger matching (hit/miss/any/disabled) unit-tested; EDID parser in place
- Clean VM (Ubuntu 26.04): smoke tests 29/29, watch startup OK

### Known issues
- Detecting a "specific display" requires it to be powered on (EDID readable); powered-off displays don't appear in the list
- Rare displays that only enter DPMS sleep without any event rely on polling fallback (detected within ~30s)

## [0.2.0-beta.1] - 2026-08-12

BETA 0.2: L2 TV box (kiosk) mode.

- L2 kiosk session: labwc compositor + dedicated TVIEW session (no desktop environment); remote is the only entry point; exiting returns to the login screen
- Runtime mode selection in Settings: TV box mode / Desktop mode (GNOME + auto-start) / Normal login (switches GDM autologin session)
- VNC remote (wayvnc): auto-starts in box mode, listens on 0.0.0.0:5900, optional password (`vnc_password`)
- Window switching via `wlrctl window focus tview` (verified)
- Installer: interactive questions (auto-start default yes; box mode default), `--no-ask`/`--desktop-mode`/`--no-autostart`
- English branding (removed "QiShi" pinyin), bilingual docs (README.en.md, RELEASE_NOTES.en.md)
- Known: VNC input unavailable in GPU-less VMs (headless lacks virtual-pointer protocol); fine on real hardware

## [0.1.0-beta.1] - 2026-08-12

First BETA release. Full launcher + Waydroid + keyd remote, installer rebuilt in "guided download" mode (no third-party proprietary assets bundled).

- Auto-start bug fix (sync autostart file on startup)
- About dialog with version
- Exit locks screen by default (security)
- App menu entry + icon
- Installer: 11 steps, dynamic Ubuntu codename for waydroid repo, no false-success reports
- CI: build + smoke test + Release publishing, all green
- GitHub Actions, MIT license, screenshots, bilingual docs
