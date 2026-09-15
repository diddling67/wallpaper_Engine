import os
import time
import hashlib
import threading
from pathlib import Path

import requests as _requests

_session: _requests.Session | None = None
_session_lock = threading.Lock()


def get_session() -> _requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = _requests.Session()
                adapter = _requests.adapters.HTTPAdapter(
                    pool_connections=4, pool_maxsize=8, max_retries=1
                )
                _session.mount("https://", adapter)
                _session.mount("http://", adapter)
    return _session


class CacheManager:
    def __init__(self, max_size_mb: int = 300):
        self.cache_dir = Path(os.environ.get("TEMP", os.path.expanduser("~"))) / "archimg_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()
        self._access_times: dict[str, float] = {}
        self._file_sizes: dict[str, int] = {}
        self._evicting = False

    def get_cache_path(self, url: str) -> Path:
        ext = self._guess_ext(url)
        name = hashlib.md5(url.encode()).hexdigest() + ext
        return self.cache_dir / name

    def download(self, url: str, timeout: int = 20) -> Path | None:
        cache_path = self.get_cache_path(url)
        if cache_path.exists():
            self._touch(str(cache_path))
            return cache_path

        try:
            sess = get_session()
            resp = sess.get(url, timeout=timeout, stream=True)
            resp.raise_for_status()
            with open(cache_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    f.write(chunk)
            size = cache_path.stat().st_size
            with self._lock:
                self._file_sizes[str(cache_path)] = size
            self._touch(str(cache_path))
            self._schedule_evict()
            return cache_path
        except Exception:
            if cache_path.exists():
                cache_path.unlink(missing_ok=True)
            return None

    def download_thumb(self, url: str, max_size: tuple[int, int] = (400, 300), timeout: int = 10):
        from PIL import Image
        import io

        cache_path = self.get_cache_path(url)
        if cache_path.exists():
            self._touch(str(cache_path))
            try:
                img = Image.open(cache_path)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                return img
            except Exception:
                return None

        try:
            sess = get_session()
            resp = sess.get(url, timeout=timeout)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            return img
        except Exception:
            return None

    def _touch(self, path: str):
        with self._lock:
            self._access_times[path] = time.time()

    def _schedule_evict(self):
        if self._evicting:
            return
        self._evicting = True
        threading.Thread(target=self._evict_if_needed, daemon=True).start()

    def _evict_if_needed(self):
        try:
            with self._lock:
                total = 0
                files = []
                for f in self.cache_dir.iterdir():
                    if f.is_file():
                        fp = str(f)
                        size = self._file_sizes.get(fp) or f.stat().st_size
                        self._file_sizes[fp] = size
                        total += size
                        atime = self._access_times.get(fp, f.stat().st_mtime)
                        files.append((atime, size, f))

                if total <= self.max_size_bytes:
                    self._evicting = False
                    return

                files.sort(key=lambda x: x[0])
                for _, size, f in files:
                    if total <= self.max_size_bytes * 0.7:
                        break
                    fp = str(f)
                    f.unlink(missing_ok=True)
                    total -= size
                    self._access_times.pop(fp, None)
                    self._file_sizes.pop(fp, None)
        finally:
            self._evicting = False

    def clear(self):
        with self._lock:
            for f in self.cache_dir.iterdir():
                if f.is_file():
                    f.unlink(missing_ok=True)
            self._access_times.clear()
            self._file_sizes.clear()

    def _guess_ext(self, url: str) -> str:
        path = url.split("?")[0]
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
            if path.lower().endswith(ext):
                return ext
        return ".jpg"
