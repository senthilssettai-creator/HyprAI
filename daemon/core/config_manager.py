import configparser
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.config_path = Path.home() / ".config" / "hyprai" / "config.ini"
        self.config = configparser.ConfigParser()
        if self.config_path.exists():
            self.config.read(self.config_path)

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback) if self.config.has_section(section) else fallback

    def get_bool(self, section, key, fallback=False):
        try:
            return self.config.getboolean(section, key)
        except Exception:
            return fallback

    def get_int(self, section, key, fallback=0):
        try:
            return self.config.getint(section, key)
        except Exception:
            return fallback
