# ☕ KeepAlive

A macOS menu bar app that keeps your Teams (or Slack, Zoom, etc.) status active by simulating user presence. It prevents idle detection using an invisible F15 keypress and disables system sleep using `caffeinate`.

---

## 📦 Features

- ✅ Prevents macOS from sleeping
- ⌨️ Simulates background F15 keypresses when idle > 4 min
- 🕘 Runs on weekdays 8:30 AM–5:30 PM (with small randomness)
- 🟢 Status icon (`🟢☕`) indicates running mode
- 🪵 Logs activity to `~/keepalive.log` (now using `Path.home()` for macOS app compatibility)
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

This creates `KeepAlive-<version>.dmg` with drag-to-Applications support.

---

## 🔐 System Permissions

Allow the app to control input:
> System Settings → Privacy & Security → Accessibility  
> ✅ Check `KeepAlive.app` or the terminal you're using

---

## 🚀 Automated GitHub Releases

Every time you tag a version (e.g., `v1.1.1`), GitHub Actions will:

- Build your `.app` using `py2app`
- Run `build-dmg.sh` to package the `.dmg`
- Upload the `.dmg` to a new GitHub Release automatically

### To trigger:

```bash
git tag v1.1.1
git push github v1.1.1
```

---

## 📄 Version

**Current: 1.1.1**

### Changelog

- **1.1.1** – Fixed logging bug by switching to `Path.home()` for compatibility inside `.app`
- **1.1.0** – Added green status icon, DMG support, removed deprecated API
- **1.0.0** – First release

---

## 🧾 License & Attribution

MIT License

> Coffee icon generated via ChatGPT with a public domain-style prompt. Free for commercial and open-source use.
