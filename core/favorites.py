import os
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from sources.base import WallpaperItem


class FavoritesManager:
    def __init__(self):
        self.config_dir = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "archimg_wallpaper"
        self.config_dir.mkdir(exist_ok=True)
        self.fav_file = self.config_dir / "favorites.md"
        self._lock = threading.Lock()
        self._liked_urls: set[str] = set()
        self._items: list[WallpaperItem] = []
        self._unavailable: list[dict] = []
        self._load()

    def _load(self):
        if not self.fav_file.exists():
            return
        try:
            content = self.fav_file.read_text(encoding="utf-8")
            self._parse_md(content)
        except Exception:
            pass

    def _parse_md(self, content: str):
        self._items.clear()
        self._liked_urls.clear()
        self._unavailable.clear()

        in_liked = False
        in_removed = False

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            low = stripped.lower()
            if low.startswith("## liked"):
                in_liked, in_removed = True, False
                continue
            elif low.startswith("## removed"):
                in_liked, in_removed = False, True
                continue
            elif stripped.startswith("## "):
                in_liked, in_removed = False, False
                continue

            if in_liked and stripped.startswith("- "):
                item = self._parse_item_line(stripped[2:])
                if item:
                    self._items.append(item)
                    self._liked_urls.add(item.url)
            elif in_removed and stripped.startswith("- "):
                self._unavailable.append(self._parse_removed_line(stripped[2:]))

    def _parse_item_line(self, line: str) -> WallpaperItem | None:
        parts = [p.strip() for p in line.split("|")]
        if not parts:
            return None
        url = parts[0]
        if not url.startswith(("http://", "https://")):
            return None
        source = parts[1] if len(parts) > 1 else "Unknown"
        category = parts[2] if len(parts) > 2 else None
        resolution = parts[3] if len(parts) > 3 else None
        title = url.split("/")[-1].rsplit(".", 1)[0]
        return WallpaperItem(
            url=url, source_name=source, title=title,
            category=category, resolution=resolution,
        )

    def _parse_removed_line(self, line: str) -> dict:
        parts = [p.strip() for p in line.split("|")]
        return {"url": parts[0] if parts else "", "reason": parts[1] if len(parts) > 1 else "Unknown"}

    def _save(self):
        lines = ["# Wallpaper Engine Favorites", "", "## Liked Wallpapers"]
        for item in self._items:
            parts = [item.url, item.source_name, item.category or "", item.resolution or ""]
            lines.append("- " + " | ".join(parts))
        lines.append("")
        if self._unavailable:
            lines.append("## Removed (Unavailable)")
            for entry in self._unavailable:
                lines.append(f"- {entry['url']} | {entry['reason']}")
            lines.append("")
        try:
            self.fav_file.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass

    def is_liked(self, url: str) -> bool:
        return url in self._liked_urls

    def toggle_like(self, item: WallpaperItem) -> bool:
        with self._lock:
            if item.url in self._liked_urls:
                self._liked_urls.discard(item.url)
                self._items = [i for i in self._items if i.url != item.url]
                self._save()
                return False
            else:
                self._liked_urls.add(item.url)
                self._items.append(item)
                self._save()
                return True

    def get_liked(self) -> list[WallpaperItem]:
        with self._lock:
            return list(self._items)

    def get_liked_urls(self) -> set[str]:
        with self._lock:
            return set(self._liked_urls)

    def get_count(self) -> int:
        return len(self._items)

    def check_availability(self, on_complete=None):
        def _do():
            from core.cache import get_session

            sess = get_session()
            items_snapshot = self.get_liked()
            if not items_snapshot:
                if on_complete:
                    on_complete(0, [])
                return

            to_remove = []
            checked = []

            def check_one(item):
                try:
                    resp = sess.head(item.url, timeout=6, allow_redirects=True)
                    if resp.status_code >= 400:
                        return (item, f"HTTP {resp.status_code}")
                    return (item, None)
                except Exception as e:
                    return (item, str(e)[:50])

            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {pool.submit(check_one, item): item for item in items_snapshot}
                for future in as_completed(futures):
                    item, error = future.result()
                    if error:
                        to_remove.append((item, error))
                    else:
                        checked.append(item)

            with self._lock:
                for item, reason in to_remove:
                    if item.url in self._liked_urls:
                        self._liked_urls.discard(item.url)
                        self._items = [i for i in self._items if i.url != item.url]
                        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                        self._unavailable.append({
                            "url": item.url,
                            "reason": f"Removed on {ts} - {reason}",
                        })
                self._save()

            if on_complete:
                on_complete(len(to_remove), checked)

        threading.Thread(target=_do, daemon=True).start()

    def remove_unavailable_entry(self, url: str):
        with self._lock:
            self._unavailable = [u for u in self._unavailable if u["url"] != url]
            self._save()
