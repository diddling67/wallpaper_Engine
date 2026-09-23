from core.cache import get_session
from sources.base import WallpaperSource, WallpaperItem


class OpenverseSource(WallpaperSource):
    name = "Openverse"
    supports_search = True
    supports_categories = False

    API_BASE = "https://api.openverse.org/v1/images/"

    def fetch_wallpapers(
        self, query: str = None, category: str = None, limit: int = 20
    ) -> list[WallpaperItem]:
        params = {
            "aspect_ratio": "wide",
            "page_size": min(limit, 50),
            "q": query or "wallpaper nature landscape",
        }

        try:
            resp = get_session().get(self.API_BASE, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for r in data.get("results", []):
                w = r.get("width", 0)
                h = r.get("height", 0)
                url = r.get("url", "")
                if not url:
                    continue
                items.append(
                    WallpaperItem(
                        url=url,
                        source_name=self.name,
                        title=r.get("title", "Openverse") or "Openverse",
                        resolution=f"{w}x{h}" if w and h else None,
                        thumbnail_url=r.get("thumbnail"),
                    )
                )
            return items[:limit]
        except Exception:
            return []

    def get_search_placeholder(self) -> str:
        return "Search: nature, landscape, sunset..."

    def is_available(self) -> bool:
        try:
            resp = get_session().get(
                self.API_BASE, params={"page_size": 1, "q": "wallpaper"}, timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False
