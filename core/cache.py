import os
import time
import hashlib
import threading
import tempfile
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
                    pool_connections=6, pool_maxsize=10, max_retries=2
                )
                _session.mount("https://", adapter)
                _session.mount("http://", adapter)
                _session.headers.update({
                    "User-Agent": "ArchImgWallpaper/2.0",
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                })
    return _session


class CacheManager:
    def __init__(self, max_size_mb: int = 500):
        self.cache_dir = Path(tempfile.gettempdir()) / "archimg_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()
        self._access_times: dict[str, float] = {}
        self._file_sizes: dict[str, int] = {}
        self._evicting = False
        self._download_locks: dict[str, threading.Lock] = {}

    def get_cache_path(self, url: str) -> Path:
        ext = self._guess_ext(url)
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{url_hash}{ext}"

    def _get_download_lock(self, url: str) -> threading.Lock:
        with self._lock:
            if url not in self._download_locks:
                self._download_locks[url] = threading.Lock()
            return self._download_locks[url]

    def download(self, url: str, timeout: int = 30) -> Path | None:
        cache_path = self.get_cache_path(url)
        dl_lock = self._get_download_lock(url)
        with dl_lock:
            if cache_path.exists() and cache_path.stat().st_size > 0:
                self._touch(str(cache_path))
                return cache_path

            try:
                sess = get_session()
                resp = sess.get(url, timeout=timeout, stream=True)
                resp.raise_for_status()
                tmp_path = cache_path.with_suffix(".tmp")
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                size = tmp_path.stat().st_size
                if size == 0:
                    tmp_path.unlink(missing_ok=True)
                    return None
                tmp_path.replace(cache_path)
                with self._lock:
                    self._file_sizes[str(cache_path)] = size
                self._touch(str(cache_path))
                self._schedule_evict()
                return cache_path
            except Exception:
                tmp_path = cache_path.with_suffix(".tmp")
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                if cache_path.exists():
                    cache_path.unlink(missing_ok=True)
                return None

    def download_thumb(
        self, url: str, max_size: tuple[int, int] = (400, 300), timeout: int = 12
    ):
        from PIL import Image
        import io

        cache_path = self.get_cache_path(url)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            self._touch(str(cache_path))
            try:
                img = Image.open(cache_path)
                img.load()
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                return img
            except Exception:
                return None

        try:
            sess = get_session()
            resp = sess.get(url, timeout=timeout)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            img.load()
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
            files = []
            total = 0
            for f in self.cache_dir.iterdir():
                if f.is_file():
                    fp = str(f)
                    try:
                        size = f.stat().st_size
                    except Exception:
                        continue
                    total += size
                    files.append((f.stat().st_mtime, size, f))

            if total <= self.max_size_bytes:
                self._evicting = False
                return

            files.sort(key=lambda x: x[0])
            evicted = set()
            for _, size, f in files:
                if total <= self.max_size_bytes * 0.6:
                    break
                fp = str(f)
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
                total -= size
                evicted.add(fp)

            with self._lock:
                for fp in evicted:
                    self._access_times.pop(fp, None)
                    self._file_sizes.pop(fp, None)

                for url in list(self._download_locks.keys()):
                    if str(self.get_cache_path(url)) in evicted:
                        self._download_locks.pop(url, None)
        finally:
            self._evicting = False

    def get_cache_size_mb(self) -> float:
        total = 0
        try:
            for f in self.cache_dir.iterdir():
                if f.is_file():
                    total += f.stat().st_size
        except Exception:
            pass
        return total / (1024 * 1024)

    def clear(self):
        files_to_delete = []
        try:
            for f in self.cache_dir.iterdir():
                if f.is_file():
                    files_to_delete.append(f)
        except Exception:
            pass
        for f in files_to_delete:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        with self._lock:
            self._access_times.clear()
            self._file_sizes.clear()
            self._download_locks.clear()

    def _guess_ext(self, url: str) -> str:
        path = url.split("?")[0].lower()
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
            if path.endswith(ext):
                return ext
        return ".jpg"
