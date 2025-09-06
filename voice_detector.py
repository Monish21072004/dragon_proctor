import time
import threading
import logging
import win32gui


class WindowTracker:
    def __init__(self, poll_interval=0.5, callback=None):
        self.poll_interval = poll_interval
        self.callback = callback
        self.current_window = None
        self.current_start_time = None
        self.event_log = []
        self.running = False
        self.risk_score = 0
        self.logger = logging.getLogger("WindowTracker")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def get_active_window(self):
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd)

    def _poll(self):
        while self.running:
            active_window = self.get_active_window()
            now = time.time()

            # Initialization: first run.
            if self.current_window is None:
                self.current_window = active_window
                self.current_start_time = now

            # When a window change is detected.
            if active_window.lower() != self.current_window.lower():
                duration = now - self.current_start_time
                # Calculate duration risk: +10 points for every 20 seconds.
                duration_risk = int(duration // 20) * 10
                # Tab switch risk: +20 points.
                switch_risk = 20
                total_risk = switch_risk + duration_risk

                # Update risk score.
                self.risk_score += total_risk

                event = {
                    "timestamp": self.current_start_time,
                    "window": self.current_window,
                    "duration": duration,
                    "risk": total_risk,
                    "details": f"Tab switch risk +{switch_risk}, Duration risk +{duration_risk}"
                }
                self.event_log.append(event)
                self.logger.info("Window changed: '%s' was active for %.2f seconds; risk +%d",
                                 self.current_window, duration, total_risk)
                if self.callback:
                    self.callback(event)

                # Update for new window.
                self.current_window = active_window
                self.current_start_time = now

            time.sleep(self.poll_interval)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()
        self.logger.info("WindowTracker started.")

    def stop(self):
        self.running = False
        self.thread.join()
        self.logger.info("WindowTracker stopped.")


if __name__ == '__main__':
    tracker = WindowTracker(callback=lambda event: print("Window Event:", event))
    tracker.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        tracker.stop()
