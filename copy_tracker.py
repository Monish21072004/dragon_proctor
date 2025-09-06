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
        self.risk_score = 0
        self.last_event_time = None
        self.event_count = 0
        self.keyboard_listener = None

        self.logger = logging.getLogger("CopyTracker")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # --- FINAL FIX: A robust stateful listener approach ---
        # This set will hold all keys that are currently pressed down.
        self.pressed_keys = set()

        # Define the combinations to block. A combination is a frozenset of keys.
        self.blocked_combinations = [
            frozenset([keyboard.Key.ctrl, keyboard.KeyCode.from_char('c')]),
            frozenset([keyboard.Key.ctrl, keyboard.KeyCode.from_char('v')]),
            frozenset([keyboard.Key.ctrl, keyboard.KeyCode.from_char('x')]),
            frozenset([keyboard.Key.ctrl, keyboard.KeyCode.from_char('a')]),
            frozenset([keyboard.Key.alt, keyboard.Key.tab]),
            frozenset([keyboard.Key.alt_l, keyboard.Key.tab]),
            frozenset([keyboard.Key.alt_r, keyboard.Key.tab]),
            frozenset([keyboard.Key.alt, keyboard.Key.f4]),
            frozenset([keyboard.Key.alt_l, keyboard.Key.f4]),
            frozenset([keyboard.Key.alt_r, keyboard.Key.f4]),
        ]

    def on_press(self, key):
        """When a key is pressed, add it to the set and check for blocked combinations."""
        if not self.shortcuts_disabled:
            return True

        # For modifiers like Ctrl, Alt, pynput sometimes sends a generic version.
        # We normalize it to the left-side version for consistency.
        if key == keyboard.Key.ctrl_r: key = keyboard.Key.ctrl
        if key == keyboard.Key.alt_r: key = keyboard.Key.alt

        # Add the newly pressed key to our set of currently held keys.
        self.pressed_keys.add(key)

        # Check if the set of currently pressed keys matches any blocked combination.
        for combination in self.blocked_combinations:
            if combination.issubset(self.pressed_keys):
                self.logger.info(f"Blocked shortcut combination: {combination}")
                return False  # Suppress the key press

        return True  # Allow the key press

    def on_release(self, key):
        """When a key is released, remove it from the set."""
        if not self.shortcuts_disabled:
            return True

        # Normalize the key on release as well
        if key == keyboard.Key.ctrl_r: key = keyboard.Key.ctrl
        if key == keyboard.Key.alt_r: key = keyboard.Key.alt

        try:
            self.pressed_keys.remove(key)
        except KeyError:
            # This can happen if the listener starts after a key was already held down.
            pass
        return True

    def disable_shortcuts(self):
        """Starts the listener to block shortcuts."""
        if not self.shortcuts_disabled:
            self.shortcuts_disabled = True
            if self.keyboard_listener is None:
                # The listener with suppress=True will block keys if on_press returns False.
                self.keyboard_listener = keyboard.Listener(
                    on_press=self.on_press,
                    on_release=self.on_release,
                    suppress=True
                )
                self.keyboard_listener.start()
            self.logger.info("Keyboard shortcut blocking enabled.")
            return True
        return False

    def enable_shortcuts(self):
        """Stops the listener to allow all shortcuts."""
        if self.shortcuts_disabled:
            self.shortcuts_disabled = False
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
            self.pressed_keys.clear()  # Clear any lingering keys
            self.logger.info("Keyboard shortcut blocking disabled.")
            return True
        return False

    def poll_clipboard(self):
        while self.running:
            try:
                text = pyperclip.paste()
                if text != self.last_clipboard and text.strip() != "":
                    current_time = time.time()
                    word_count = len(text.split())
                    base_risk = (word_count // 10) * 10

                    if self.last_event_time and (current_time - self.last_event_time) < 60:
                        self.event_count += 1
                    else:
                        self.event_count = 1
                    self.last_event_time = current_time

                    multiplier = 2 ** (self.event_count - 1)
                    risk_increment = base_risk * multiplier
                    self.risk_score += risk_increment

                    event = {
                        "timestamp": current_time, "event": "Copy-Paste Detected",
                        "content_preview": text[:50], "word_count": word_count,
                        "risk": risk_increment
                    }
                    self.event_log.append(event)
                    if self.callback:
                        self.callback(event)
                    self.last_clipboard = text
            except Exception as e:
                self.logger.debug("Could not read clipboard: %s", e)

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

    print("Starting test... Shortcuts will be disabled in 5 seconds.")
    time.sleep(5)
    tracker.disable_shortcuts()
    print("Shortcuts disabled. Try typing normally, then try Ctrl+C, Alt+Tab, etc.")

    time.sleep(15)
    tracker.enable_shortcuts()
    print("Shortcuts enabled again.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        tracker.stop()
