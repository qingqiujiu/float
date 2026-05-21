import json
import os
from .usage_snapshot import UsageSnapshot
from .config_manager import ConfigManager


class CacheManager:
    def __init__(self):
        self._path = ConfigManager.cache_path()
        self._memory: UsageSnapshot | None = None

    def save(self, snapshot: UsageSnapshot):
        self._memory = snapshot
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get_last(self) -> UsageSnapshot | None:
        if self._memory is not None:
            return self._memory
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._memory = UsageSnapshot.from_dict(data)
                return self._memory
            except (json.JSONDecodeError, KeyError, ValueError):
                return None
        return None

    def clear(self):
        self._memory = None
        if os.path.exists(self._path):
            os.remove(self._path)
