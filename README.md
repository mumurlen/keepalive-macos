# ☕ KeepAlive

A macOS menu bar app that keeps your Teams (or Slack, Zoom, etc.) status active by simulating user presence. It prevents idle detection using an invisible F15 keypress and disables system sleep using `caffeinate`.

---

## 📦 Features

- ✅ Prevents macOS from sleeping
- ⌨️ Simulates background F15 keypresses when idle > customizable threshold
- 🕘 Runs on weekdays 8:30 AM–5:30 PM (with small randomness)
- ⚙️ Settings window lets you adjust idle timeout (default: 240s)
- 🪵 Logs to `~/keepalive.log` and prunes it daily
- 🟢 Status icon (`🟢☕`) indicates running mode
- 📦 Built with `rumps`, packaged as `.app` and `.dmg`

---

## 📄 Version

**Current: 1.1.3**

### Changelog

- **1.1.3** – Automatically prunes `keepalive.log` once per day

---

## 🛠 How to Build

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup.py py2app
```

To generate a `.dmg`, run:

```bash
./build-dmg.sh
```
