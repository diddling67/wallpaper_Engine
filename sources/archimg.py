import requests
from sources.base import WallpaperSource, WallpaperItem


class ArchImgSource(WallpaperSource):
    name = "ArchImg"
    supports_search = False
    supports_categories = False

    MANIFEST_URL = "https://archimg.cc/image-manifest.txt"
    BASE_URL = "https://archimg.cc/assets/"

    def fetch_wallpapers(
        self, query: str = None, category: str = None, limit: int = 24
    ) -> list[WallpaperItem]:
        try:
            resp = requests.get(self.MANIFEST_URL, timeout=15)
            resp.raise_for_status()
            lines = [
                l.strip()
                for l in resp.text.splitlines()
                if l.strip()
                and any(
                    l.strip().lower().endswith(ext)
                    for ext in [".jpg", ".jpeg", ".png", ".webp"]
                )
            ]
            items = [
                WallpaperItem(
                    url=self.BASE_URL + name,
                    source_name=self.name,
                    title=name,
                )
                for name in lines
            ]
            if limit:
                items = items[:limit]
            return items
        except Exception:
            return []

    def is_available(self) -> bool:
        try:
            resp = requests.head(self.MANIFEST_URL, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
