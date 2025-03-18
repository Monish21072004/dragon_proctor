import subprocess
import logging

class NetworkLockdown:
    def __init__(self, allowed_exe):
        self.allowed_exe = allowed_exe  # Full path to the allowed exam browser, e.g., "C:\\Program Files\\ExamBrowser\\exam.exe"
        self.active = False
        self.logger = logging.getLogger("NetworkLockdown")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def activate(self):
        try:
            # Method 1: Set global outbound policy to block for all profiles
            subprocess.run('netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound', shell=True, check=True)
            self.logger.info("Global outbound policy set to block.")
        except Exception as e:
            self.logger.error("Error setting global firewall policy: %s", e)
        try:
            # Remove any pre-existing block rule (if exists)
            subprocess.run('netsh advfirewall firewall delete rule name="BlockAllOutbound"', shell=True)
        except Exception as e:
            self.logger.warning("No existing BlockAllOutbound rule to delete: %s", e)
        try:
            # Method 2: Explicitly add a rule to block all outbound traffic
            subprocess.run('netsh advfirewall firewall add rule name="BlockAllOutbound" dir=out action=block', shell=True, check=True)
            self.logger.info("Explicit outbound block rule added.")
        except Exception as e:
            self.logger.error("Error adding outbound block rule: %s", e)
        try:
            # Add an exception rule for the allowed exam application
            subprocess.run(f'netsh advfirewall firewall add rule name="AllowExam" dir=out action=allow program="{self.allowed_exe}"', shell=True, check=True)
            self.logger.info("Allowed rule for exam browser added.")
            self.active = True
        except Exception as e:
            self.logger.error("Error adding allowed rule: %s", e)

    def deactivate(self):
        try:
            # Reset the firewall to its default settings
            subprocess.run('netsh advfirewall reset', shell=True, check=True)
            self.logger.info("Network lockdown deactivated and firewall reset to default.")
            self.active = False
        except Exception as e:
            self.logger.error("Failed to deactivate network lockdown: %s", e)
