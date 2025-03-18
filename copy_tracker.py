import time
import threading
import logging
import pyperclip
from pynput import keyboard


class CopyTracker:
    def __init__(self, poll_interval=1.0, callback=None):
        self.poll_interval = poll_interval
        self.callback = callback
        self.event_log = []
        self.last_clipboard = ""
        self.running = False
        self.shortcuts_disabled = False
        self.risk_score = 0  # cumulative risk score for copy events
        # For exponential risk in a one-minute window.
        self.last_event_time = None
        self.event_count = 0  # number of events within the last minute
        self.keyboard_listener = None

        self.logger = logging.getLogger("CopyTracker")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Define the shortcuts to block
        self.blocked_shortcuts = [
            {keyboard.Key.ctrl, keyboard.KeyCode.from_char('c')},  # Ctrl+C
            {keyboard.Key.ctrl, keyboard.KeyCode.from_char('v')},  # Ctrl+V
            {keyboard.Key.ctrl, keyboard.KeyCode.from_char('x')},  # Ctrl+X
            {keyboard.Key.ctrl, keyboard.KeyCode.from_char('a')},  # Ctrl+A
            {keyboard.Key.ctrl, keyboard.KeyCode.from_char('z')},  # Ctrl+Z
            {keyboard.Key.alt, keyboard.Key.tab},  # Alt+Tab
            {keyboard.Key.alt, keyboard.Key.f4}  # Alt+F4
        ]
        self.current_keys = set()

    def on_press(self, key):
        if not self.shortcuts_disabled:
            return True

        try:
            self.current_keys.add(key)
            for shortcut in self.blocked_shortcuts:
                if all(k in self.current_keys for k in shortcut):
                    self.logger.info(f"Blocked shortcut: {shortcut}")
                    return False  # Block the key
        except Exception as e:
            self.logger.error(f"Error in on_press: {e}")
        return True

    def on_release(self, key):
        try:
            self.current_keys.discard(key)
        except Exception as e:
            self.logger.error(f"Error in on_release: {e}")
        return True

    def disable_shortcuts(self):
        """Disable keyboard shortcuts like Ctrl+C, Ctrl+V, etc."""
        if not self.shortcuts_disabled:
            self.shortcuts_disabled = True
            if self.keyboard_listener is None:
                self.keyboard_listener = keyboard.Listener(
                    on_press=self.on_press,
                    on_release=self.on_release,
                    suppress=True  # This prevents the keys from propagating to the system.
                )
                self.keyboard_listener.start()
            self.logger.info("Keyboard shortcuts disabled")
            return True
        return False

    def enable_shortcuts(self):
        """Enable keyboard shortcuts"""
        if self.shortcuts_disabled:
            self.shortcuts_disabled = False
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None  # Reset the listener so it can be recreated later if needed.
            self.logger.info("Keyboard shortcuts enabled")
            return True
        return False

    def poll_clipboard(self):
        while self.running:
            try:
                text = pyperclip.paste()
            except Exception as e:
                self.logger.error("Error reading clipboard: %s", e)
                text = ""
            # Check if clipboard content has changed and is not empty.
            if text != self.last_clipboard and text.strip() != "":
                current_time = time.time()
                word_count = len(text.split())
                # Base risk: +10 points per 10 words.
                base_risk = (word_count // 10) * 10
                # Check if the event is within 60 seconds of the previous event.
                if self.last_event_time and (current_time - self.last_event_time) < 60:
                    self.event_count += 1
                else:
                    self.event_count = 1
                self.last_event_time = current_time

                # Exponential multiplier: for instance, risk multiplied by 2^(n-1)
                multiplier = 2 ** (self.event_count - 1)
                risk_increment = base_risk * multiplier

                self.risk_score += risk_increment

                event = {
                    "timestamp": current_time,
                    "event": "Copy-Paste Detected",
                    "content_preview": text[:50],
                    "word_count": word_count,
                    "risk": risk_increment,
                    "multiplier": multiplier,
                    "event_count": self.event_count
                }
                self.event_log.append(event)
                self.logger.info("Copy detected. Words: %d, Base risk: %d, Multiplier: %d, Total risk increment: %d",
                                 word_count, base_risk, multiplier, risk_increment)
                if self.callback:
                    self.callback(event)
                self.last_clipboard = text
            time.sleep(self.poll_interval)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.poll_clipboard, daemon=True)
        self.thread.start()
        self.logger.info("CopyTracker started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        self.logger.info("CopyTracker stopped.")


if __name__ == "__main__":
    def event_callback(event):
        print("Copy Event:", event)


    tracker = CopyTracker(callback=event_callback)
    tracker.start()

    # Example of disabling shortcuts after 5 seconds
    time.sleep(5)
    tracker.disable_shortcuts()
    print("Shortcuts disabled. Try using Ctrl+C, Ctrl+V, etc.")

    # Example of enabling shortcuts after another 10 seconds
    time.sleep(10)
    tracker.enable_shortcuts()
    print("Shortcuts enabled again.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        tracker.stop()
