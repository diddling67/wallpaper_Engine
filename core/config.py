import json
import os
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
}


class Config:
    def __init__(self):
        self.config_dir = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "archimg_wallpaper"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    saved = json.load(f)
                self.data.update(saved)
            except Exception:
                pass

    def save(self):
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()

    def update(self, updates: dict):
        self.data.update(updates)
        self.save()
