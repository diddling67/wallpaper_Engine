from core.cache import get_session
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
            resp = get_session().get(self.MANIFEST_URL, timeout=15)
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
            if query:
                q = query.lower()
                lines = [l for l in lines if q in l.lower()]
            items = [
                WallpaperItem(
                    url=self.BASE_URL + name,
                    source_name=self.name,
                    title=name.rsplit(".", 1)[0],
                )
                for name in lines
            ]
            return items[:limit] if limit else items
        except Exception:
            return []

    def is_available(self) -> bool:
        try:
            resp = get_session().head(self.MANIFEST_URL, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
