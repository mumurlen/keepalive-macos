# ☕ KeepAlive

A macOS menu bar app that keeps your status active in Microsoft Teams (or similar apps) by simulating periodic keyboard activity. Designed to run quietly in the background during work hours, it prevents system sleep and triggers fake activity only when idle.

---

## 📦 Features

- ✅ Prevents macOS from sleeping using `caffeinate`
- 💤 Simulates invisible keypress (`F15`) only when idle > 4 minutes
- 📅 Weekday-only schedule from 8:30 AM to 5:30 PM (with slight random variation)
- 🔄 Green icon indicator (`🟢☕`) when running
- 🪵 Logs activity and system idle state to `~/keepalive.log`
- 🧠 Built with `rumps` for a native macOS menu bar experience

---

## 🔧 Requirements

- macOS Ventura or newer
- Python 3.8+
- `rumps` library

Install with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install rumps
```

---

## 🚀 How to Run

```bash
source .venv/bin/activate
python keepalive.py
```

You’ll see a ☕ icon in your macOS menu bar. When running, it becomes 🟢☕.

---

## 📄 Version

**Current version: 1.1.0**

### Changelog

- `v1.1.0`: Added visual menu bar indicator (🟢☕) when running
- `v1.0.0`: Initial release with idle detection, keypress simulation, and system sleep prevention

---

## 📁 File Structure

```
keepalive/
├── keepalive.py         # Main script
├── README.md            # This file
├── requirements.txt     # Python dependencies
└── .venv/               # Python virtual environment (optional)
```

---

## 📝 License

MIT 
