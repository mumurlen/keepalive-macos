# ☕ KeepAlive

A macOS menu bar app that keeps your Teams (or Slack, Zoom, etc.) status active by simulating user presence. It prevents idle detection using an invisible F15 keypress and disables system sleep using `caffeinate`.

---

## 📦 Features

- ✅ Prevents macOS from sleeping
- ⌨️ Simulates background F15 keypresses when idle > customizable threshold
- 🕘 Runs on weekdays 8:30 AM–5:30 PM (with small randomness)
- 🟢 Status icon (`🟢☕`) indicates running mode
- ⚙️ New: Settings window lets you adjust idle timeout (default: 240s)
- 🪵 Logs to `~/keepalive.log`
- 📦 Built with `rumps`, packaged as `.app` and `.dmg`

---

## 📄 Version

**Current: 1.1.2**

### Changelog

- **1.1.2** – Added settings dialog to customize idle timeout
