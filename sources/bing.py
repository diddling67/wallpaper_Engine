import requests
from sources.base import WallpaperSource, WallpaperItem


class BingSource(WallpaperSource):
    name = "Bing Daily"
    supports_search = False
    supports_categories = False

    API_URL = "https://bing.biturl.top/"

    def fetch_wallpapers(
        self, query: str = None, category: str = None, limit: int = 1
    ) -> list[WallpaperItem]:
        items = []
        for idx in range(min(limit, 8)):
            try:
                resp = requests.get(
                    self.API_URL,
                    params={"resolution": "UHD", "format": "json", "index": str(idx), "mkt": "en-US"},
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                url = data.get("url", "")
                if url:
                    items.append(
                        WallpaperItem(
                            url=url,
                            source_name=self.name,
                            title=data.get("copyright", f"Bing Day {idx}")[:80],
                        )
                    )
            except Exception:
                continue
        return items

    def is_available(self) -> bool:
        try:
            resp = requests.get(
                self.API_URL,
                params={"resolution": "1920x1080", "format": "json", "index": "0", "mkt": "en-US"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False
