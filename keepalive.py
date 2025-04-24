import rumps
import subprocess
import datetime
import time
import threading
import random
from pathlib import Path

__version__ = "1.1.2"

LOG_FILE = str(Path.home() / "keepalive.log")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.datetime.now()} - {msg}\n")

class KeepAliveApp(rumps.App):
    def __init__(self):
        super().__init__("☕", quit_button=None)
        self.menu = ["Start", "Stop", "Settings", None, "Quit"]
        self.running = False
        self.thread = None
        self.last_day = datetime.datetime.now().day
        self.start_variation = random.randint(-10, 10)
        self.end_variation = random.randint(-10, 10)
        self.idle_limit = 240  # default 4 minutes

    def simulate_key(self):
        try:
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 113'])
            log("F15 keypress sent.")
        except Exception as e:
            log(f"Failed to simulate key: {e}")

    def check_idle_time(self):
        try:
            output = subprocess.check_output(
                "ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print $NF/1000000000; exit}'",
                shell=True
            )
            return float(output.strip())
        except:
            return 0

    def run_loop(self):
        while self.running:
            now = datetime.datetime.now()
            if now.day != self.last_day:
                self.last_day = now.day
                self.start_variation = random.randint(-10, 10)
                self.end_variation = random.randint(-10, 10)

            if now.weekday() < 5:
                total_minutes = now.hour * 60 + now.minute
                start_time = 510 + self.start_variation
                end_time = 1050 + self.end_variation

                if start_time <= total_minutes <= end_time:
                    idle = self.check_idle_time()
                    if idle >= self.idle_limit:
                        self.simulate_key()
                    else:
                        log(f"User active (idle {idle:.0f}s) — no action.")
                else:
                    log("Outside work hours.")
            else:
                log("Weekend — idle check skipped.")

            time.sleep(240)

    @rumps.clicked("Start")
    def start(self, _):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run_loop, daemon=True)
            self.thread.start()
            self.title = "🟢☕"
            log("Started keepalive loop.")

    @rumps.clicked("Stop")
    def stop(self, _):
        self.running = False
        self.title = "☕"
        log("Stopped keepalive loop.")

    @rumps.clicked("Settings")
    def settings(self, _):
        response = rumps.Window(
            title="Idle Limit",
            message="Enter new idle threshold in seconds (default is 240):",
            default_text=str(self.idle_limit),
            ok="Set"
        ).run()
        if response.clicked and response.text.isdigit():
            self.idle_limit = int(response.text)
            log(f"Idle threshold updated to {self.idle_limit} seconds.")

    @rumps.clicked("Quit")
    def quit_app(self, _):
        self.stop(_)
        rumps.quit_application()

if __name__ == "__main__":
    KeepAliveApp().run()
