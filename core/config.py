import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

DEFAULT_CONFIG = {
    "interval": 30,
    "style": "Fill",
    "shuffle": True,
    "auto_start": False,
    "minimize_to_tray": True,
    "playlist_mode": "merged",
    "active_source": None,
    "enabled_sources": ["ArchImg", "Wallhaven"],
    "wallhaven_query": "",
    "wallhaven_categories": ["100"],
    "wallhaven_min_resolution": "1920x1080",
    "wallhaven_max_results": 50,
    "wallhaven_api_key": "",
    "wallwidgy_category": "all",
    "wallwidgy_color": "all",
    "openverse_query": "nature wallpaper",
    "custom_sources": [],
    "theme": "dark",
    "window_geometry": "",
    "max_cache_mb": 500,
}


class Config:
    def __init__(self):
        self.config_dir = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "archimg_wallpaper"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.data = dict(DEFAULT_CONFIG)
        self._lock = threading.Lock()
        self._save_timer: threading.Timer | None = None
        self.load()

    def load(self):
        if self.config_file.exists():
            try:
                content = self.config_file.read_text(encoding="utf-8")
                saved = json.loads(content)
                self.data.update(saved)
            except Exception:
                pass

    def save(self):
        with self._lock:
            snapshot = dict(self.data)
        try:
            tmp = self.config_file.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            tmp.replace(self.config_file)
        except Exception:
            pass

    def _schedule_save(self):
        if self._save_timer:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(0.5, self.save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def get(self, key: str, default=None):
        with self._lock:
            return self.data.get(key, default)

    def set(self, key: str, value):
        with self._lock:
            self.data[key] = value
        self._schedule_save()

    def update(self, updates: dict):
        with self._lock:
            self.data.update(updates)
        self._schedule_save()

    def set_immediate(self, key: str, value):
        with self._lock:
            self.data[key] = value
        self.save()
