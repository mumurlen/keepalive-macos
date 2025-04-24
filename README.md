# ☕ KeepAlive

A macOS menu bar app that keeps your status active in Microsoft Teams (or similar apps) by simulating harmless background activity. It helps prevent "Away" status during work hours by sending F15 key presses only when the system is idle.

---

## 📦 Features

- ✅ Prevents macOS sleep with `caffeinate`
- ⏱️ Simulates keypress (F15) if idle for over 4 minutes
- 📅 Weekday-only schedule: 8:30 AM to 5:30 PM (with small random variation)
- 🟢 Status icon (🟢☕) shows when running
- 🪵 Logs to `~/keepalive.log`
- 💻 Built with `rumps` for macOS menu bar integration
- 📦 Distributed as a `.app` and optionally `.dmg` installer

---

## 🚀 Getting Started

### 1. Clone and install requirements

```bash
git clone git@github.com:mumurlen/keepalive-macos.git
cd keepalive-macos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the app manually

```bash
python keepalive.py
```

---

## 📁 Packaging the App

### Build `.app` with py2app:

```bash
python setup.py py2app
```

### Create `.dmg` installer (optional)

```bash
./build-dmg.sh
```

> Make sure to install `create-dmg` via Homebrew: `brew install create-dmg`

---

## 🔐 Permissions

To simulate keyboard input, grant **Accessibility** permission:

> System Settings → Privacy & Security → Accessibility  
> ✅ Enable for `KeepAlive.app` or your terminal if running it directly

---

## 🧾 License & Attribution

MIT License

> The coffee icon was generated via ChatGPT using a public domain-style prompt. No copyright restrictions.

---

## 📌 Version

Current: `v1.1.0`

### Changelog

- **1.1.0** – Added green status icon, removed deprecated Carbon call
- **1.0.0** – Initial release with keypress + sleep prevention

---
