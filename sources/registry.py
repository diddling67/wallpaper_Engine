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
    def __init__(self):
        self.sources: dict[str, WallpaperSource] = {}
        self._init_builtin()

    def _init_builtin(self):
        for name, cls in BUILTIN_SOURCES.items():
            self.sources[name] = cls()

    def add_custom(self, url: str, name: str) -> CustomSource:
        src = CustomSource(url, name)
        self.sources[name] = src
        return src

    def remove(self, name: str):
        if name in self.sources and name not in BUILTIN_SOURCES:
            del self.sources[name]

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
        for name in enabled_names:
            src = self.sources.get(name)
            if src:
                try:
                    items = src.fetch_wallpapers(
                        query=query, category=category, limit=limit_per_source
                    )
                    all_items.extend(items)
                except Exception:
                    continue
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
