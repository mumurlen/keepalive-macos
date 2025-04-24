# keepalive.py - Menu Bar App to Keep Teams Active
# Author: Mihai (via ChatGPT)
# Description: macOS menu bar app that prevents system sleep and simulates keypresses

import rumps
import subprocess
import datetime
import time
import threading
import random
import os

# Path to log file for debugging and validation
LOG_FILE = os.path.expanduser("~/keepalive.log")

class KeepAliveApp(rumps.App):
    def __init__(self):
        # Initialize the menu bar app with a coffee emoji and remove default quit
        super(KeepAliveApp, self).__init__("☕", quit_button=None)
        self.title = "☕"  # Menu bar icon

        # Runtime state variables
        self.running = False
        self.thread = None
        self.caffeinate_proc = None

        # Daily variation setup to simulate natural behavior
        self.last_day = datetime.datetime.now().day
        self.start_variation = random.randint(-10, 10)
        self.end_variation = random.randint(-10, 10)

        # Menu structure
        self.menu = [
            rumps.MenuItem("Start", callback=self.start),
            rumps.MenuItem("Stop", callback=self.stop),
            None,
            rumps.MenuItem("View Log", callback=self.view_log),
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]

    # Write logs with timestamps to a file for debugging and traceability
    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    # Start caffeinate to prevent the system from sleeping
    def start_caffeinate(self):
        self.caffeinate_proc = subprocess.Popen(["caffeinate", "-dimsu"])
        self.log("Started caffeinate.")

    # Stop the caffeinate process if running
    def stop_caffeinate(self):
        if self.caffeinate_proc:
            self.caffeinate_proc.terminate()
            self.log("Stopped caffeinate.")
            self.caffeinate_proc = None

    # Simulate a key press (F15) to reset user idle state without visible side effects
    def simulate_key(self):
        try:
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 113'])
            self.log("Simulated F15 key press.")
        except Exception as e:
            self.log(f"Failed to simulate key: {e}")

    # Use ioreg to read macOS idle time in seconds
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

    # Main logic loop to simulate human-like activity only during work hours and if idle
    def run_loop(self):
        self.log("KeepAlive loop started.")
        while self.running:
            now = datetime.datetime.now()

            # If a new day has started, re-randomize variations
            if now.day != self.last_day:
                self.last_day = now.day
                self.start_variation = random.randint(-10, 10)
                self.end_variation = random.randint(-10, 10)
                self.log(f"New day: start variation={self.start_variation}, end variation={self.end_variation}")

            # Check only on weekdays
            if now.weekday() < 5:
                total_minutes = now.hour * 60 + now.minute
                start_time = 510 + self.start_variation   # 8:30 AM
                end_time = 1050 + self.end_variation      # 5:30 PM

                if start_time <= total_minutes <= end_time:
                    idle_time = self.get_idle_time()
                    if idle_time >= 240:  # 4 minutes
                        self.simulate_key()
                    else:
                        self.log(f"Idle: {int(idle_time)}s — no action.")
                else:
                    self.log("Outside work hours.")
            else:
                self.log("Weekend — skipping activity check.")

            time.sleep(240)  # Wait 4 minutes before next check

        self.log("KeepAlive loop stopped.")

    # Starts the keep-alive thread and caffeinate
    def start(self, _):
        if not self.running:
            self.running = True
            self.start_caffeinate()
            self.thread = threading.Thread(target=self.run_loop, daemon=True)
            self.thread.start()
            self.log("Started KeepAlive.")

    # Stops the loop and caffeinate
    def stop(self, _):
        if self.running:
            self.running = False
            self.stop_caffeinate()
            self.log("Stopped KeepAlive.")

    # Opens the log file in TextEdit for quick review
    def view_log(self, _):
        subprocess.run(["open", "-a", "TextEdit", LOG_FILE])

    # Clean shutdown via menu Quit item
    def quit_app(self, _):
        self.running = False
        self.stop_caffeinate()
        self.log("Quitting KeepAlive.")
        rumps.quit_application()

# Launch the app
if __name__ == "__main__":
    KeepAliveApp().run()

