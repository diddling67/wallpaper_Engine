from concurrent.futures import ThreadPoolExecutor, as_completed

from sources.archimg import ArchImgSource
from sources.wallhaven import WallhavenSource
from sources.wallwidgy import WallwidgySource
from sources.openverse import OpenverseSource
from sources.custom import CustomSource
from sources.base import WallpaperSource, WallpaperItem


BUILTIN_SOURCES: dict[str, type[WallpaperSource]] = {
    "ArchImg": ArchImgSource,
    "Wallhaven": WallhavenSource,
    "Wallwidgy": WallwidgySource,
    "Openverse": OpenverseSource,
}


class SourceRegistry:
    def __init__(self, config=None):
        self.sources: dict[str, WallpaperSource] = {}
        self.config = config
        self._init_builtin()
        self._load_custom_sources()

    def _init_builtin(self):
        for name, cls in BUILTIN_SOURCES.items():
            self.sources[name] = cls()

    def _load_custom_sources(self):
        if not self.config:
            return
        for entry in self.config.get("custom_sources", []):
            url = entry.get("url", "")
            name = entry.get("name", "")
            if url and name and name not in self.sources:
                src = CustomSource(url, name)
                self.sources[name] = src

    def add_custom(self, url: str, name: str) -> CustomSource:
        src = CustomSource(url, name)
        self.sources[name] = src
        return src

    def remove(self, name: str):
        if name in self.sources and name not in BUILTIN_SOURCES:
            del self.sources[name]
            if self.config:
                custom = self.config.get("custom_sources", [])
                custom = [c for c in custom if c.get("name") != name]
                self.config.set("custom_sources", custom)

    def get(self, name: str) -> WallpaperSource | None:
        return self.sources.get(name)

    def get_all(self) -> dict[str, WallpaperSource]:
        return dict(self.sources)

    def get_enabled(self, enabled_names: list[str]) -> list[WallpaperSource]:
        return [self.sources[n] for n in enabled_names if n in self.sources]

    def fetch_all(
        self,
        enabled_names: list[str],
        query: str = None,
        category: str = None,
        limit_per_source: int = 50,
    ) -> list[WallpaperItem]:
        all_items = []
        sources = [(name, self.sources[name]) for name in enabled_names if name in self.sources]
        if not sources:
            return all_items

        def _fetch_one(name, src):
            try:
                return src.fetch_wallpapers(query=query, category=category, limit=limit_per_source)
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=min(len(sources), 4)) as pool:
            futures = {pool.submit(_fetch_one, name, src): name for name, src in sources}
            for future in as_completed(futures):
                try:
                    items = future.result()
                    all_items.extend(items)
                except Exception:
                    pass
        return all_items

    def fetch_source(
        self,
        name: str,
        query: str = None,
        category: str = None,
        limit: int = 50,
    ) -> list[WallpaperItem]:
        src = self.sources.get(name)
        if src:
            try:
                return src.fetch_wallpapers(query=query, category=category, limit=limit)
            except Exception:
                return []
        return []
