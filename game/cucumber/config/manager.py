import os
import yaml


class ConfigSection:
    def __init__(self, data):
        self._data = data or {}

    def get(self, key, default=None):
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    @property
    def data(self):
        return self._data


class ConfigFile:
    def __init__(self, path):
        self.path = path
        self._data = {}
        self.reload()

    def reload(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}

    def get(self, key, default=None):
        return ConfigSection(self._data).get(key, default)

    def section(self, key):
        return ConfigSection(self.get(key, {}))

    @property
    def data(self):
        return self._data


class ConfigManager:
    def __init__(self):
        self.dir = None
        self._files = {}
        self._main = None
        self._messages = None
        self._watch = False

    def load(self, config_dir):
        self.dir = config_dir
        self._main = self.file("config.yml")
        self._messages = self.file("messages.yml")
        self.file("items.yml")

    def file(self, filename):
        if filename not in self._files:
            path = os.path.join(self.dir, filename) if self.dir else filename
            self._files[filename] = ConfigFile(path)
        return self._files[filename]

    def get(self, key, default=None):
        if self._main is None:
            return default
        return self._main.get(key, default)

    def message(self, key, **placeholders):
        if self._messages is None:
            return None
        text = self._messages.get(key)
        if text is None:
            return None
        for ph, value in placeholders.items():
            text = text.replace("{" + ph + "}", str(value))
        return text

    def reload(self):
        for f in self._files.values():
            f.reload()

    def watch(self, enabled=True):
        self._watch = enabled


config = ConfigManager()
