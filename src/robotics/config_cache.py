# Config Cache — mtime-based auto-refresh for servo_config.json
# Caches configuration in memory, reloads only when file changes.

import os
import json
from pathlib import Path


class ConfigCache:
    """
    servo_config.json cache with mtime-based auto-refresh.

    - First call: lazy file load
    - Subsequent calls: mtime comparison, reload only if changed
    - invalidate(): explicit cache reset
    """

    def __init__(self):
        self._config = None
        self._mtime = 0
        self._path = Path(__file__).parent.parent.parent / "servo_config.json"

    def get(self):
        """Return cached config. Auto-refresh if file changed."""
        current_mtime = os.path.getmtime(self._path)
        if self._config is None or current_mtime != self._mtime:
            with open(self._path, 'r') as f:
                self._config = json.load(f)
            self._mtime = current_mtime
        return self._config

    def invalidate(self):
        """Force cache invalidation. Next get() will reload from disk."""
        self._config = None
        self._mtime = 0

    def get_arm(self, arm_name):
        """Return config for a specific arm."""
        config = self.get()
        return config.get(arm_name, {})

    def get_geometry(self):
        """Return geometry section."""
        config = self.get()
        return config.get("geometry", {})


# Module-level singleton
_cache = ConfigCache()


def get_config():
    """Return singleton cache instance."""
    return _cache
