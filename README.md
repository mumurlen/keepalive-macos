# ☕ KeepAlive

A simple macOS menu bar app that keeps Microsoft Teams (or any activity-based status app) from switching you to "Away" by simulating periodic activity. It uses `rumps` to run a lightweight menu bar app and `caffeinate` to prevent system sleep.

---

## 🚀 Features

- 🕒 Simulates activity only during work hours (8:30 AM to 5:30 PM ± random offset)
- 💤 Triggers only if system has been idle for 4+ minutes
- 🔐 Sends harmless F15 keypress (invisible)
- ☕ Prevents system sleep using `caffeinate`
- 📄 Logs all actions to `~/keepalive.log`
- 💼 macOS native menu bar interface

## ✅ Updates
 

- 🟢 **Green dot + coffee cup** (`🟢☕`) when **running**
- ☕ **Plain coffee cup** when **stopped or idle**

This gives you instant visual feedback in the menu bar.

---

## 📦 Requirements

- macOS (tested on Ventura and later)
- Python 3.8+
- [`rumps`](https://github.com/jaredks/rumps)

Install requirements in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 🔧 Running the App

```bash
source .venv/bin/activate
python keepalive.py
```

☕ A coffee cup will appear in your macOS menu bar. Use it to:

- Start/Stop the simulation
- View the log file
- Quit the app

---

## 📁 Project Structure

```
keepalive/
├── keepalive.py         # Main app script
├── requirements.txt     # Python dependencies
├── README.md            # You're reading it
└── .venv/               # Virtual environment (excluded in .gitignore)
```

---

## 🛑 Quitting the App

Use the menu bar → Quit option. The app shuts down cleanly and stops all background threads and sleep prevention.

---

## 📝 License

MIT License 
