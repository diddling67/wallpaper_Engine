import threading
import random
from sources.base import WallpaperItem


class SlideshowEngine:
    def __init__(self, on_change_callback=None):
        self.playlist: list[WallpaperItem] = []
        self.current_index: int = 0
        self.interval: int = 30
        self.shuffle: bool = True
        self.playing: bool = False
        self._timer: threading.Timer | None = None
        self._on_change = on_change_callback
        self._lock = threading.Lock()
        self._order: list[int] = []
        self._changing = False

    def set_playlist(self, items: list[WallpaperItem]):
        with self._lock:
            self.playlist = list(items)
            self._build_order()
            self.current_index = 0

    def _build_order(self):
        n = len(self.playlist)
        self._order = list(range(n))
        if self.shuffle:
            random.shuffle(self._order)

    def get_current(self) -> WallpaperItem | None:
        with self._lock:
            if not self.playlist or not self._order:
                return None
            idx = self._order[self.current_index % len(self._order)]
            return self.playlist[idx]

    def get_position(self) -> tuple[int, int]:
        with self._lock:
            return self.current_index + 1, len(self.playlist)

    def next(self) -> WallpaperItem | None:
        with self._lock:
            if not self.playlist or not self._order:
                return None
            self.current_index = (self.current_index + 1) % len(self._order)
            idx = self._order[self.current_index]
            return self.playlist[idx]

    def previous(self) -> WallpaperItem | None:
        with self._lock:
            if not self.playlist or not self._order:
                return None
            self.current_index = (self.current_index - 1) % len(self._order)
            idx = self._order[self.current_index]
            return self.playlist[idx]

    def start(self):
        self.playing = True
        self._schedule_next()

    def stop(self):
        self.playing = False
        self._cancel_timer()

    def toggle(self):
        if self.playing:
            self.stop()
        else:
            self.start()

    def _cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self):
        if not self.playing:
            return
        self._cancel_timer()
        self._timer = threading.Timer(self.interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self):
        if not self.playing or self._changing:
            return
        self._changing = True
        try:
            item = self.next()
            if item and self._on_change:
                self._on_change(item)
        finally:
            self._changing = False
        if self.playing:
            self._schedule_next()

    def reshuffle(self):
        with self._lock:
            self._order = list(range(len(self.playlist)))
            random.shuffle(self._order)
            self.current_index = 0
