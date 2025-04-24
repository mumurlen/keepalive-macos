# keepalive.py - Menu Bar App to Keep Teams Active
# Author: Mihai (via ChatGPT)
# Version: 1.1.1

__version__ = "1.1.1"

import rumps
import subprocess
import datetime
import time
import threading
import random
from pathlib import Path

# Updated to use pathlib for better compatibility inside .app bundles
LOG_FILE = str(Path.home() / "keepalive.log")

class KeepAliveApp(rumps.App):
    def __init__(self):
        super(KeepAliveApp, self).__init__("☕", quit_button=None)
        self.default_title = "☕"
        self.running_title = "🟢☕"
        self.title = self.default_title

        self.running = False
        self.thread = None
        self.caffeinate_proc = None

        self.last_day = datetime.datetime.now().day
        self.start_variation = random.randint(-10, 10)
        self.end_variation = random.randint(-10, 10)

        self.menu = [
            rumps.MenuItem("Start", callback=self.start),
            rumps.MenuItem("Stop", callback=self.stop),
            None,
            rumps.MenuItem("View Log", callback=self.view_log),
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]

    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def start_caffeinate(self):
        self.caffeinate_proc = subprocess.Popen(["caffeinate", "-dimsu"])
        self.log("Started caffeinate.")

    def stop_caffeinate(self):
        if self.caffeinate_proc:
            self.caffeinate_proc.terminate()
            self.log("Stopped caffeinate.")
            self.caffeinate_proc = None

    def simulate_key(self):
        try:
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 113'])
            self.log("Simulated F15 key press.")
        except Exception as e:
            self.log(f"Failed to simulate key: {e}")

    def get_idle_time(self):
        try:
            output = subprocess.check_output(
                "ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print $NF/1000000000; exit}'",
                shell=True
            )
            return float(output.strip())
        except Exception as e:
            self.log(f"Idle time check failed: {e}")
            return 0

    def run_loop(self):
        self.log("KeepAlive loop started.")
        while self.running:
            now = datetime.datetime.now()

            if now.day != self.last_day:
                self.last_day = now.day
                self.start_variation = random.randint(-10, 10)
                self.end_variation = random.randint(-10, 10)
                self.log(f"New day: start variation={self.start_variation}, end variation={self.end_variation}")

            if now.weekday() < 5:
                total_minutes = now.hour * 60 + now.minute
                start_time = 510 + self.start_variation
                end_time = 1050 + self.end_variation

                if start_time <= total_minutes <= end_time:
                    idle_time = self.get_idle_time()
                    if idle_time >= 240:
                        self.simulate_key()
                    else:
                        self.log(f"Idle: {int(idle_time)}s — no action.")
                else:
                    self.log("Outside work hours.")
            else:
                self.log("Weekend — skipping activity check.")

            time.sleep(240)

        self.log("KeepAlive loop stopped.")

    def start(self, _):
        if not self.running:
            self.running = True
            self.title = self.running_title
            self.start_caffeinate()
            self.thread = threading.Thread(target=self.run_loop, daemon=True)
            self.thread.start()
            self.log("Started KeepAlive.")

    def stop(self, _):
        if self.running:
            self.running = False
            self.title = self.default_title
            self.stop_caffeinate()
            self.log("Stopped KeepAlive.")

    def view_log(self, _):
        subprocess.run(["open", "-a", "TextEdit", LOG_FILE])

    def quit_app(self, _):
        self.running = False
        self.title = self.default_title
        self.stop_caffeinate()
        self.log("Quitting KeepAlive.")
        rumps.quit_application()

if __name__ == "__main__":
    KeepAliveApp().run()

