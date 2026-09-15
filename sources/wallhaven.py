import requests
from sources.base import WallpaperSource, WallpaperItem


class WallhavenSource(WallpaperSource):
    name = "Wallhaven"
    supports_search = True
    supports_categories = True

    API_BASE = "https://wallhaven.cc/api/v1"
    CATEGORIES = {"General": "100", "Anime": "010", "People": "001"}

    def fetch_wallpapers(
        self, query: str = None, category: str = None, limit: int = 24
    ) -> list[WallpaperItem]:
        params = {
            "sorting": "random",
            "purity": "100",
            "atleast": "1920x1080",
            "page": 1,
        }
        if query:
            params["q"] = query
        if category and category in self.CATEGORIES:
            params["categories"] = self.CATEGORIES[category]

        pages_needed = max(1, (limit + 23) // 24)
        items = []
        for page in range(1, pages_needed + 1):
            params["page"] = page
            try:
                resp = requests.get(
                    f"{self.API_BASE}/search", params=params, timeout=15
                )
                resp.raise_for_status()
                data = resp.json()
                for wp in data.get("data", []):
                    items.append(
                        WallpaperItem(
                            url=wp["path"],
                            source_name=self.name,
                            title=wp.get("id", "unknown"),
                            category=self._cat_name(wp.get("category", "")),
                            resolution=wp.get("resolution"),
                            thumbnail_url=wp.get("thumbs", {}).get("large"),
                        )
                    )
                if len(items) >= limit:
                    break
            except Exception:
                break

        return items[:limit]

    def get_categories(self) -> list[str]:
        return list(self.CATEGORIES.keys())

    def get_search_placeholder(self) -> str:
        return "Search tags: nature, cyberpunk, linux..."

    def is_available(self) -> bool:
        try:
            resp = requests.get(
                f"{self.API_BASE}/search",
                params={"page": 1, "sorting": "random", "purity": "100"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _cat_name(self, cat_id: str) -> str:
        for name, cid in self.CATEGORIES.items():
            if cid == cat_id:
                return name
        return cat_id
