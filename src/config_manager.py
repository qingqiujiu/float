import json
import os
import shutil

DEFAULT_CONFIG = {
    "version": 1,
    "general": {
        "refresh_interval_seconds": 300,
        "window_opacity": 0.85,
        "always_on_top": True,
        "window_x": None,
        "window_y": None,
    },
    "api": {
        "api_key": "",
    },
}


def _appdata_dir() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    path = os.path.join(appdata, "float")
    os.makedirs(path, exist_ok=True)
    return path


def _config_path() -> str:
    return os.path.join(_appdata_dir(), "config.json")


def _cache_path() -> str:
    return os.path.join(_appdata_dir(), "cache.json")


class ConfigManager:
    _instance = None

    def __init__(self):
        self._data = None

    @classmethod
    def instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self) -> dict:
        path = _config_path()
        if not os.path.exists(path):
            bundled = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config.json",
            )
            if os.path.exists(bundled):
                shutil.copy(bundled, path)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)

        try:
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            backup = path + ".bak"
            if os.path.exists(path):
                os.rename(path, backup)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            self._data = dict(DEFAULT_CONFIG)

        self._ensure_keys(DEFAULT_CONFIG, self._data)
        return self._data

    def save(self):
        if self._data is None:
            return
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get_general(self) -> dict:
        if self._data is None:
            self.load()
        return self._data.get("general", DEFAULT_CONFIG["general"])

    def set_general(self, key: str, value):
        if self._data is None:
            self.load()
        self._data.setdefault("general", {})[key] = value
        self.save()

    def get_api_key(self) -> str:
        if self._data is None:
            self.load()
        return self._data.get("api", {}).get("api_key", "")

    def set_api_key(self, key: str):
        if self._data is None:
            self.load()
        self._data.setdefault("api", {})["api_key"] = key
        self.save()

    def get_window_w(self) -> int | None:
        if self._data is None:
            self.load()
        return self._data.get("general", {}).get("window_w")

    def get_window_h(self) -> int | None:
        if self._data is None:
            self.load()
        return self._data.get("general", {}).get("window_h")

    def set_window_w(self, w: int):
        if self._data is None:
            self.load()
        self._data.setdefault("general", {})["window_w"] = w
        self.save()

    def set_window_h(self, h: int):
        if self._data is None:
            self.load()
        self._data.setdefault("general", {})["window_h"] = h
        self.save()

    def get_color_theme(self) -> str:
        if self._data is None:
            self.load()
        return self._data.get("general", {}).get("color_theme", "indigo")

    def set_color_theme(self, theme: str):
        if self._data is None:
            self.load()
        self._data.setdefault("general", {})["color_theme"] = theme
        self.save()

    def get_user_token(self) -> str:
        if self._data is None:
            self.load()
        return self._data.get("api", {}).get("user_token", "")

    def set_user_token(self, token: str):
        if self._data is None:
            self.load()
        self._data.setdefault("api", {})["user_token"] = token
        self.save()

    @staticmethod
    def _ensure_keys(default: dict, target: dict):
        for k, v in default.items():
            if k not in target:
                target[k] = v
            elif isinstance(v, dict) and isinstance(target.get(k), dict):
                ConfigManager._ensure_keys(v, target[k])

    @staticmethod
    def cache_path() -> str:
        return _cache_path()
