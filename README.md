# ☕ KeepAlive

A macOS menu bar app that keeps your Teams (or Slack, Zoom, etc.) status active by simulating user presence. It prevents idle detection using an invisible F15 keypress and disables system sleep using `caffeinate`.

---

## 📦 Features

- ✅ Prevents macOS from sleeping
- ⌨️ Simulates background F15 keypresses when idle > 4 min
- 🕘 Runs on weekdays 8:30 AM–5:30 PM (with small randomness)
- 🟢 Status icon (`🟢☕`) indicates running mode
- 🪵 Logs activity to `~/keepalive.log`
- 📦 Built with `rumps`, packaged as `.app` and `.dmg`

---

## 🛠 How to Build

### Clone & install dependencies

```bash
git clone git@github.com:mumurlen/keepalive-macos.git
cd keepalive-macos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Build `.app` with py2app

```bash
python setup.py py2app
```

Your app will be created in: `dist/KeepAlive.app`

---

## 📦 Create a .dmg Installer

### 1. Install create-dmg (if needed)

```bash
brew install create-dmg
```

### 2. Run the script

```bash
./build-dmg.sh
```

This creates `KeepAlive-1.1.0.dmg` with drag-to-Applications support.

---

## 🔐 System Permissions

Allow the app to control input:
> System Settings → Privacy & Security → Accessibility  
> ✅ Check `KeepAlive.app` or the terminal you're using

---

## 📄 Version

**Current: 1.1.0**

### Changelog

- **1.1.0** – Added green status icon, DMG support, removed deprecated API
- **1.0.0** – First release

---

## 🧾 License & Attribution

MIT License

> Coffee icon generated via ChatGPT with a public domain-style prompt. Free for commercial and open-source use.
