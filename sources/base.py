from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class WallpaperItem:
    url: str
    source_name: str
    title: str
    category: str | None = None
    resolution: str | None = None
    thumbnail_url: str | None = None


@dataclass
class CompatibilityResult:
    compatible: bool
    source_type: str = "unknown"
    categories: list[str] = field(default_factory=list)
    image_count: int = 0
    supports_search: bool = False
    supports_categories: bool = False
    error_message: str = ""


class WallpaperSource(ABC):
    name: str = "Unknown"
    supports_search: bool = False
    supports_categories: bool = False

    @abstractmethod
    def fetch_wallpapers(
        self, query: str = None, category: str = None, limit: int = 24
    ) -> list[WallpaperItem]: ...

    def get_categories(self) -> list[str]:
        return []

    @abstractmethod
    def is_available(self) -> bool: ...

    def get_search_placeholder(self) -> str:
        return ""
