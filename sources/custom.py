import re
import requests
from bs4 import BeautifulSoup
from sources.base import WallpaperSource, WallpaperItem, CompatibilityResult

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
MANIFEST_PATHS = [
    "/image-manifest.txt",
    "/index.json",
    "/catalog/index.json",
    "/all.json",
    "/api/images",
    "/images.json",
    "/wallpapers.json",
]
API_PATTERNS = [
    "?format=json",
    "&format=json",
    "?json=true",
    "/api/v1/search",
    "/api/wallpapers",
    "/api/images",
]
OPENAPI_PATHS = ["/openapi.json", "/swagger.json", "/.well-known/schema-discovery"]


class CustomSource(WallpaperSource):
    name = "Custom"
    supports_search = False
    supports_categories = False

    def __init__(self, url: str, source_name: str = "Custom Source"):
        self.base_url = url.rstrip("/")
        self.name = source_name
        self._image_urls: list[str] = []
        self._categories: list[str] = []
        self._compatibility: CompatibilityResult | None = None

    def fetch_wallpapers(
        self, query: str = None, category: str = None, limit: int = 24
    ) -> list[WallpaperItem]:
        if self._image_urls:
            items = [
                WallpaperItem(
                    url=u,
                    source_name=self.name,
                    title=u.split("/")[-1].rsplit(".", 1)[0],
                )
                for u in self._image_urls
            ]
            return items[:limit]
        return []

    def get_categories(self) -> list[str]:
        return self._categories

    def is_available(self) -> bool:
        try:
            resp = requests.head(self.base_url, timeout=10)
            return resp.status_code < 500
        except Exception:
            return False

    def probe(self) -> CompatibilityResult:
        result = CompatibilityResult(compatible=False)
        headers = {"User-Agent": "ArchImgWallpaper/1.0"}

        for path in MANIFEST_PATHS:
            try:
                resp = requests.get(self.base_url + path, headers=headers, timeout=10)
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    if "json" in ct or path.endswith(".json"):
                        data = resp.json()
                        urls = self._extract_urls_from_json(data)
                        if urls:
                            result.compatible = True
                            result.source_type = "json_api"
                            result.image_count = len(urls)
                            self._image_urls = urls
                            cats = self._extract_categories_from_json(data)
                            if cats:
                                result.categories = cats
                                result.supports_categories = True
                                self._categories = cats
                            return result
                    elif path.endswith(".txt"):
                        lines = [
                            l.strip()
                            for l in resp.text.splitlines()
                            if l.strip()
                            and any(
                                l.strip().lower().endswith(e) for e in IMAGE_EXTS
                            )
                        ]
                        if lines:
                            result.compatible = True
                            result.source_type = "manifest"
                            result.image_count = len(lines)
                            self._image_urls = [
                                self.base_url + "/assets/" + l for l in lines
                            ]
                            return result
            except Exception:
                continue

        for pattern in API_PATTERNS:
            try:
                test_url = self.base_url + pattern
                resp = requests.get(test_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    if "json" in ct:
                        data = resp.json()
                        urls = self._extract_urls_from_json(data)
                        if urls:
                            result.compatible = True
                            result.source_type = "rest_api"
                            result.image_count = len(urls)
                            self._image_urls = urls
                            return result
            except Exception:
                continue

        for path in OPENAPI_PATHS:
            try:
                resp = requests.get(self.base_url + path, headers=headers, timeout=10)
                if resp.status_code == 200 and "json" in resp.headers.get(
                    "Content-Type", ""
                ):
                    result.compatible = True
                    result.source_type = "openapi"
                    result.error_message = "OpenAPI found but endpoints need manual configuration"
                    return result
            except Exception:
                continue

        try:
            resp = requests.get(self.base_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                img_urls = []
                for img in soup.find_all("img", src=True):
                    src = img["src"]
                    if any(src.lower().endswith(e) for e in IMAGE_EXTS):
                        if not src.startswith("http"):
                            src = self.base_url + "/" + src.lstrip("/")
                        img_urls.append(src)
                if img_urls:
                    result.compatible = True
                    result.source_type = "html_scrape"
                    result.image_count = len(img_urls)
                    self._image_urls = img_urls[:50]
                    return result
        except Exception:
            pass

        result.error_message = (
            "Could not find compatible API, manifest, or image listings at this URL. "
            "The site may require authentication, use a non-standard format, or not serve wallpapers."
        )
        return result

    def _extract_urls_from_json(self, data, depth=0) -> list[str]:
        if depth > 5:
            return []
        urls = []
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, str) and any(
                    val.lower().endswith(e) for e in IMAGE_EXTS
                ):
                    urls.append(val)
                elif isinstance(val, (dict, list)):
                    urls.extend(self._extract_urls_from_json(val, depth + 1))
            if "url" in data and isinstance(data["url"], str):
                u = data["url"]
                if any(u.lower().endswith(e) for e in IMAGE_EXTS):
                    urls.append(u)
        elif isinstance(data, list):
            for item in data:
                urls.extend(self._extract_urls_from_json(item, depth + 1))
        return urls

    def _extract_categories_from_json(self, data) -> list[str]:
        cats = set()
        if isinstance(data, dict):
            if "files" in data and isinstance(data["files"], list):
                for f in data["files"]:
                    if isinstance(f, dict) and "category" in f:
                        cats.add(f["category"])
            if "category" in data and isinstance(data["category"], str):
                cats.add(data["category"])
            if "categories" in data and isinstance(data["categories"], list):
                for c in data["categories"]:
                    if isinstance(c, str):
                        cats.add(c)
                    elif isinstance(c, dict) and "name" in c:
                        cats.add(c["name"])
        elif isinstance(data, list):
            for item in data[:50]:
                if isinstance(item, dict):
                    if "category" in item and isinstance(item["category"], str):
                        cats.add(item["category"])
                    if "categories" in item and isinstance(item["categories"], str):
                        cats.add(item["categories"])
        return sorted(cats)
