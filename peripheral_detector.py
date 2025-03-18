import time
import threading
import logging
import wmi
import win32api
import pythoncom

class PeripheralDetector:
    def __init__(self, callback=None):
        self.callback = callback  # Callback function when an event is detected
        self.event_log = []       # List to store peripheral events
        self.running = False
        self.risk_score = 0       # Cumulative risk score for peripheral detection
        self.last_monitor_count = 0  # Track previous monitor count
        self.logger = logging.getLogger("PeripheralDetector")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def monitor_pnp(self):
        # Initialize COM for this thread.
        pythoncom.CoInitialize()
        c = wmi.WMI()
        watcher = c.watch_for(notification_type="Creation", wmi_class="Win32_PnPEntity")
        while self.running:
            try:
                event = watcher(timeout_ms=5000)
                if event:
                    risk_inc = 35
                    self.risk_score += risk_inc
                    log_entry = {
                        "timestamp": time.time(),
                        "device": event.Caption,
                        "risk": risk_inc
                    }
                    self.event_log.append(log_entry)
                    self.logger.info("New peripheral detected: %s; risk increased by %d", event.Caption, risk_inc)
                    if self.callback:
                        self.callback(log_entry)
            except wmi.x_wmi_timed_out:
                continue
            except Exception as e:
                self.logger.error("Error in monitor_pnp: %s", e)
                time.sleep(1)
        pythoncom.CoUninitialize()

    def monitor_monitors(self):
        while self.running:
            try:
                monitors = win32api.EnumDisplayMonitors()
                count = len(monitors)
                if count != self.last_monitor_count:
                    if count > 1:
                        risk_inc = 35
                        self.risk_score += risk_inc
                        log_entry = {
                            "timestamp": time.time(),
                            "device": f"Multiple monitors detected: {count}",
                            "risk": risk_inc
                        }
                        self.event_log.append(log_entry)
                        self.logger.info("Multiple monitors detected (%d monitors); risk increased by %d", count, risk_inc)
                        if self.callback:
                            self.callback(log_entry)
                    self.last_monitor_count = count
            except Exception as e:
                self.logger.error("Error checking monitors: %s", e)
            time.sleep(5)

    def start(self):
        self.running = True
        self.thread_pnp = threading.Thread(target=self.monitor_pnp, daemon=True)
        self.thread_monitors = threading.Thread(target=self.monitor_monitors, daemon=True)
        self.thread_pnp.start()
        self.thread_monitors.start()
        self.logger.info("PeripheralDetector started.")

    def stop(self):
        self.running = False
        self.thread_pnp.join()
        self.thread_monitors.join()
        self.logger.info("PeripheralDetector stopped.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    detector = PeripheralDetector(callback=lambda event: print("Detected:", event))
    detector.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        detector.stop()
