"""Configuration management"""
import configparser
from pathlib import Path


class ConfigManager:
    def __init__(self):
        self.config_path = Path.home() / '.config/hyprai/config.ini'
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)
    
    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)
    
    def get_int(self, section, key, fallback=0):
        return self.config.getint(section, key, fallback=fallback)
    
    def get_bool(self, section, key, fallback=False):
        return self.config.getboolean(section, key, fallback=fallback)
    
    @property
    def gemini_key(self):
        return self.get('api', 'gemini_key')
    
    @property
    def model(self):
        return self.get('api', 'model', 'gemini-1.5-flash')
    
    @property
    def db_path(self):
        return Path(self.get('system', 'db_path'))
    
    @property
    def port(self):
        return self.get_int('system', 'port', 8765)