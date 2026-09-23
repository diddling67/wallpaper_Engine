from core.cache import get_session
from sources.base import WallpaperSource, WallpaperItem


class WallwidgySource(WallpaperSource):
    name = "Wallwidgy"
    supports_search = False
    supports_categories = True

    API_BASE = "https://wallwidgy.vercel.app/api/wallpapers"
    CATEGORIES = [
        "all", "abstract", "anime", "architecture", "art",
        "cars", "minimal", "nature", "tech",
    ]
    COLORS = [
        "all", "blue", "red", "green", "purple",
        "pink", "orange", "yellow", "black", "white",
    ]

    def __init__(self):
        self.category = "all"
        self.color = "all"

    def fetch_wallpapers(
        self, query: str = None, category: str = None, limit: int = 10
    ) -> list[WallpaperItem]:
        params = {"type": "desktop", "count": min(limit, 10)}
        cat = category or self.category
        if cat and cat != "all":
            params["category"] = cat
        if self.color and self.color != "all":
            params["color"] = self.color

        try:
            resp = get_session().get(self.API_BASE, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for url in data.get("wallpapers", []):
                name = url.split("/")[-1].rsplit(".", 1)[0]
                items.append(
                    WallpaperItem(
                        url=url,
                        source_name=self.name,
                        title=name,
                        category=data.get("category", "all"),
                    )
                )
            return items
        except Exception:
            return []

    def get_categories(self) -> list[str]:
        return self.CATEGORIES

    def is_available(self) -> bool:
        try:
            resp = get_session().get(
                self.API_BASE, params={"type": "desktop", "count": 1}, timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False
