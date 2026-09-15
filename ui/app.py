import threading
import customtkinter as ctk
from PIL import Image
import io
import requests

from sources.registry import SourceRegistry
from sources.base import WallpaperItem
from core.cache import CacheManager
from core.config import Config
from core.slideshow import SlideshowEngine
from core.favorites import FavoritesManager
from core.wallpaper import set_wallpaper, get_screen_resolution
from core.autostart import is_autostart_enabled, set_autostart

PREVIEW_MAX = (400, 300)
FAV_PREVIEW_MAX = (500, 250)


class ArchImgApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = Config()
        self.registry = SourceRegistry()
        self.cache = CacheManager()
        self.favorites = FavoritesManager()
        self.engine = SlideshowEngine(on_change_callback=self._on_wallpaper_change)

        screen_w, screen_h = get_screen_resolution()
        win_w = max(750, int(screen_w * 0.55))
        win_h = max(550, int(screen_h * 0.70))

        self.title("Wallpaper Engine")
        self.geometry(f"{win_w}x{win_h}")
        self.minsize(700, 500)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._current_item: WallpaperItem | None = None
        self._preview_image = None
        self._fav_preview_image = None
        self._seconds_left = 0
        self._countdown_id = None
        self._active_tab = "browse"
        self._apply_seq = 0
        self._preview_size = (500, 300)
        self._search_after_id = None
        self._interval_after_id = None
        self._closed = False
        self._fav_selected_url = None

        self._tray_icon = None

        self._build_ui()
        self._load_settings()
        self._refresh_sources()

        self.bind("<Configure>", self._on_configure)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._start_tray)
        self.after(1000, self._check_favorites_availability)

    def _on_configure(self, event=None):
        if event and event.widget == self:
            pw = max(100, self.winfo_width() - 40)
            ph = max(100, self.winfo_height() - 250)
            self._preview_size = (pw, ph)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)

        self._build_tab_bar()
        self._build_browse_tab()
        self._build_favorites_tab()
        self._build_controls_panel()
        self._build_status_bar()

        self._show_tab("browse")

    def _build_tab_bar(self):
        bar = ctk.CTkFrame(self, height=40, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        bar.grid_columnconfigure(2, weight=1)
        bar.grid_rowconfigure(0, weight=0)
        bar.grid_rowconfigure(1, weight=0)

        self._tab_browse_btn = ctk.CTkButton(
            bar, text="Browse", width=120, height=32,
            corner_radius=0, fg_color=("gray75", "gray25"),
            command=lambda: self._show_tab("browse"),
        )
        self._tab_browse_btn.grid(row=0, column=0, padx=(0, 2), pady=4)

        fav_count = self.favorites.get_count()
        self._tab_fav_btn = ctk.CTkButton(
            bar, text=f"Favorites ({fav_count})", width=140, height=32,
            corner_radius=0, fg_color=("gray75", "gray25"),
            command=lambda: self._show_tab("favorites"),
        )
        self._tab_fav_btn.grid(row=0, column=1, padx=(2, 0), pady=4)

        self._like_btn = ctk.CTkButton(
            bar, text="Like", width=60, height=32,
            corner_radius=0, fg_color=("gray75", "gray25"),
            command=self._on_toggle_like,
        )
        self._like_btn.grid(row=0, column=3, padx=10, pady=4)

        self._tab_indicator = ctk.CTkLabel(bar, text="", width=120, height=2, fg_color="#2196F3")
        self._tab_indicator.grid(row=1, column=0, sticky="sw")

    def _show_tab(self, tab: str):
        self._active_tab = tab
        if tab == "browse":
            self._browse_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
            self._fav_frame.grid_forget()
            self._tab_indicator.grid(row=1, column=0, sticky="sw")
        else:
            self._browse_frame.grid_forget()
            self._fav_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
            self._tab_indicator.grid(row=1, column=1, sticky="sw")
            self._refresh_favorites_list()

    def _build_browse_tab(self):
        self._browse_frame = ctk.CTkFrame(self)
        self._browse_frame.grid_columnconfigure(0, weight=1)
        self._browse_frame.grid_rowconfigure(2, weight=1)

        self._build_source_panel()
        self._build_search_panel()
        self._build_preview_panel()

    def _build_favorites_tab(self):
        self._fav_frame = ctk.CTkFrame(self)
        self._fav_frame.grid_columnconfigure(0, weight=1)
        self._fav_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self._fav_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header.grid_columnconfigure(1, weight=1)

        self._fav_title_label = ctk.CTkLabel(
            header, text=f"Your Favorites ({self.favorites.get_count()})",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._fav_title_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="Check Availability", width=140,
            command=self._on_check_fav_availability,
        ).grid(row=0, column=1, sticky="e")

        self._fav_list_frame = ctk.CTkScrollableFrame(self._fav_frame)
        self._fav_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self._fav_list_frame.grid_columnconfigure(0, weight=1)
        self._fav_rows: list[ctk.CTkFrame] = []

        self._fav_preview_frame = ctk.CTkFrame(self._fav_frame, height=180)
        self._fav_preview_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
        self._fav_preview_frame.grid_columnconfigure(0, weight=1)

        self._fav_preview_label = ctk.CTkLabel(
            self._fav_preview_frame, text="Select a favorite to preview", text_color="gray",
        )
        self._fav_preview_label.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self._fav_preview_info = ctk.CTkLabel(
            self._fav_preview_frame, text="", font=ctk.CTkFont(size=10), text_color="gray",
        )
        self._fav_preview_info.grid(row=1, column=0, padx=10, pady=(0, 5))

        fav_btn_frame = ctk.CTkFrame(self._fav_frame, fg_color="transparent")
        fav_btn_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))

        ctk.CTkButton(
            fav_btn_frame, text="Play Favorites", width=120,
            command=self._on_play_favorites,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            fav_btn_frame, text="Remove Selected", width=120, fg_color="#cc3333",
            command=self._on_remove_selected_fav,
        ).pack(side="right", padx=5)

    def _build_source_panel(self):
        frame = ctk.CTkFrame(self._browse_frame)
        frame.grid(row=0, column=0, padx=10, pady=(5, 3), sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Sources:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(10, 5), pady=5
        )

        self._source_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._source_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self._source_checkboxes: dict[str, ctk.CTkCheckBox] = {}

        self._add_source_btn = ctk.CTkButton(
            frame, text="+ Add Source", width=100,
            command=self._open_add_source_dialog,
        )
        self._add_source_btn.grid(row=0, column=2, padx=10, pady=5)

        mode_frame = ctk.CTkFrame(frame, fg_color="transparent")
        mode_frame.grid(row=0, column=3, padx=10, pady=5)

        ctk.CTkLabel(mode_frame, text="Mode:").pack(side="left", padx=(0, 5))
        self._mode_var = ctk.StringVar(value=self.config.get("playlist_mode", "merged"))
        self._mode_menu = ctk.CTkOptionMenu(
            mode_frame, variable=self._mode_var,
            values=["merged", "single"], width=100,
            command=self._on_mode_change,
        )
        self._mode_menu.pack(side="left")

        self._single_source_var = ctk.StringVar(value="ArchImg")
        self._single_source_menu = ctk.CTkOptionMenu(
            mode_frame, variable=self._single_source_var,
            values=["ArchImg"], width=120,
            command=self._on_single_source_change,
        )

    def _build_search_panel(self):
        frame = ctk.CTkFrame(self._browse_frame)
        frame.grid(row=1, column=0, padx=10, pady=3, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Search:").grid(row=0, column=0, padx=(10, 5), pady=5)
        self._search_entry = ctk.CTkEntry(
            frame, placeholder_text="Search tags: nature, cyberpunk, linux...", width=300,
        )
        self._search_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self._search_btn = ctk.CTkButton(
            frame, text="Search", width=80, command=self._on_search
        )
        self._search_btn.grid(row=0, column=2, padx=5, pady=5)

        ctk.CTkLabel(frame, text="Category:").grid(row=0, column=3, padx=(15, 5), pady=5)
        self._category_var = ctk.StringVar(value="All")
        self._category_menu = ctk.CTkOptionMenu(
            frame, variable=self._category_var, values=["All"], width=120,
            command=self._on_category_change,
        )
        self._category_menu.grid(row=0, column=4, padx=5, pady=5)

    def _build_preview_panel(self):
        self._preview_frame = ctk.CTkFrame(self._browse_frame)
        self._preview_frame.grid(row=2, column=0, padx=10, pady=3, sticky="nsew")
        self._preview_frame.grid_rowconfigure(0, weight=1)
        self._preview_frame.grid_columnconfigure(0, weight=1)

        self._preview_label = ctk.CTkLabel(
            self._preview_frame, text="No wallpaper loaded", font=ctk.CTkFont(size=14),
        )
        self._preview_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self._preview_info = ctk.CTkLabel(
            self._preview_frame, text="", font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._preview_info.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="s")

    def _build_controls_panel(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=2, column=0, padx=10, pady=3, sticky="ew")
        frame.grid_columnconfigure(3, weight=1)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self._prev_btn = ctk.CTkButton(btn_frame, text="|<", width=40, command=self._on_prev)
        self._prev_btn.pack(side="left", padx=2)

        self._play_btn = ctk.CTkButton(btn_frame, text="||", width=40, command=self._on_toggle_play)
        self._play_btn.pack(side="left", padx=2)

        self._next_btn = ctk.CTkButton(btn_frame, text=">|", width=40, command=self._on_next)
        self._next_btn.pack(side="left", padx=2)

        self._shuffle_btn = ctk.CTkButton(btn_frame, text="Shuffle", width=70, command=self._on_shuffle)
        self._shuffle_btn.pack(side="left", padx=(10, 2))

        self._refresh_btn = ctk.CTkButton(btn_frame, text="Refresh", width=70, command=self._refresh_sources)
        self._refresh_btn.pack(side="left", padx=2)

        sf = ctk.CTkFrame(frame, fg_color="transparent")
        sf.grid(row=0, column=2, columnspan=2, padx=10, pady=5, sticky="e")

        ctk.CTkLabel(sf, text="Interval:").pack(side="left", padx=(0, 5))
        self._interval_slider = ctk.CTkSlider(
            sf, from_=5, to=300, number_of_steps=59, width=150,
            command=self._on_interval_change,
        )
        self._interval_slider.set(self.config.get("interval", 30))
        self._interval_slider.pack(side="left", padx=5)

        self._interval_label = ctk.CTkLabel(sf, text=f"{self.config.get('interval', 30)}s", width=40)
        self._interval_label.pack(side="left", padx=5)

        ctk.CTkLabel(sf, text="Style:").pack(side="left", padx=(10, 5))
        self._style_var = ctk.StringVar(value=self.config.get("style", "Fill"))
        self._style_menu = ctk.CTkOptionMenu(
            sf, variable=self._style_var,
            values=["Fill", "Fit", "Stretch", "Tile", "Center", "Span"],
            width=80, command=self._on_style_change,
        )
        self._style_menu.pack(side="left")

        self._autostart_var = ctk.BooleanVar(value=self.config.get("auto_start", False))
        self._autostart_cb = ctk.CTkCheckBox(
            sf, text="Auto-start", variable=self._autostart_var,
            command=self._on_autostart_toggle,
        )
        self._autostart_cb.pack(side="left", padx=(15, 5))

    def _build_status_bar(self):
        self._status_label = ctk.CTkLabel(
            self, text="Ready | Select sources and click Refresh",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w",
        )
        self._status_label.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="ew")

    def _load_settings(self):
        self._interval_slider.set(self.config.get("interval", 30))
        self._interval_label.configure(text=f"{self.config.get('interval', 30)}s")
        self.engine.interval = self.config.get("interval", 30)
        self.engine.shuffle = self.config.get("shuffle", True)
        if is_autostart_enabled():
            self._autostart_var.set(True)

    def _refresh_sources(self):
        for widget in self._source_frame.winfo_children():
            widget.destroy()
        self._source_checkboxes.clear()

        enabled = self.config.get("enabled_sources", ["ArchImg", "Wallhaven"])
        for name in self.registry.get_all():
            var = ctk.BooleanVar(value=name in enabled)
            cb = ctk.CTkCheckBox(
                self._source_frame, text=name, variable=var,
                command=lambda n=name, v=var: self._on_source_toggle(n, v.get()),
            )
            cb.pack(side="left", padx=5)
            self._source_checkboxes[name] = (cb, var)

        self._update_single_source_menu()
        self._update_categories()

    def _update_single_source_menu(self):
        names = list(self._source_checkboxes.keys())
        if names:
            self._single_source_menu.configure(values=names)
            if self._single_source_var.get() not in names:
                self._single_source_var.set(names[0])

    def _update_categories(self):
        enabled = self.config.get("enabled_sources", [])
        cats = {"All"}
        for name in enabled:
            src = self.registry.get(name)
            if src and src.supports_categories:
                for c in src.get_categories():
                    cats.add(c)
        self._category_menu.configure(values=sorted(cats))
        if self._category_var.get() not in cats:
            self._category_var.set("All")

        for n in enabled:
            src = self.registry.get(n)
            if src and src.supports_search:
                self._search_entry.configure(placeholder_text=src.get_search_placeholder())
                return

    def _on_source_toggle(self, name: str, enabled: bool):
        current = self.config.get("enabled_sources", [])
        if enabled and name not in current:
            current.append(name)
        elif not enabled and name in current:
            current.remove(name)
        self.config.set("enabled_sources", current)
        self._update_single_source_menu()
        self._update_categories()

    def _on_mode_change(self, mode: str):
        self.config.set("playlist_mode", mode)
        if mode == "single":
            self._single_source_menu.pack(side="left", padx=(5, 0))
        else:
            self._single_source_menu.pack_forget()

    def _on_single_source_change(self, source: str):
        self.config.set("active_source", source)
        if self.config.get("playlist_mode") == "single":
            self._fetch_and_load(source=source)

    def _on_search(self):
        self._fetch_and_load(query=self._search_entry.get().strip() or None)

    def _on_category_change(self, category: str):
        self._fetch_and_load(category=category if category != "All" else None)

    def _fetch_and_load(self, query=None, category=None, source=None):
        if self._closed:
            return
        self._status_label.configure(text="Fetching wallpapers...")
        self.update_idletasks()

        def _do():
            mode = self.config.get("playlist_mode", "merged")
            if mode == "single" or source:
                src_name = source or self._single_source_var.get()
                items = self.registry.fetch_source(src_name, query=query, category=category, limit=100)
            else:
                enabled = self.config.get("enabled_sources", [])
                items = self.registry.fetch_all(enabled, query=query, category=category, limit_per_source=50)
            if not self._closed:
                self.after(0, lambda: self._on_fetch_complete(items))

        threading.Thread(target=_do, daemon=True).start()

    def _on_fetch_complete(self, items: list[WallpaperItem]):
        if self._closed:
            return
        if not items:
            self._status_label.configure(text="No wallpapers found. Check source settings.")
            return

        self.engine.set_playlist(items)
        src_count = len(set(i.source_name for i in items))
        self._status_label.configure(text=f"Loaded {len(items)} wallpapers from {src_count} source(s)")

        if not self.engine.playing:
            self.engine.start()
            self._play_btn.configure(text="||")
            self._start_countdown()

        item = self.engine.get_current()
        if item:
            self._apply_wallpaper(item)

    def _on_wallpaper_change(self, item: WallpaperItem):
        if not self._closed:
            self.after(0, lambda: self._apply_wallpaper(item))

    def _apply_wallpaper(self, item: WallpaperItem):
        if self._closed:
            return
        self._current_item = item
        self._apply_seq += 1
        seq = self._apply_seq
        self._status_label.configure(text=f"Loading: {item.title} from {item.source_name}...")

        def _do():
            path = self.cache.download(item.url)
            if path and seq == self._apply_seq and not self._closed:
                style = self.config.get("style", "Fill")
                success = set_wallpaper(str(path), style)
                if not self._closed:
                    self.after(0, lambda: self._on_wallpaper_set(item, success))
            elif not self._closed and seq == self._apply_seq:
                self.after(0, lambda: self._status_label.configure(text=f"Failed: {item.title}"))

        threading.Thread(target=_do, daemon=True).start()

    def _on_wallpaper_set(self, item: WallpaperItem, success: bool):
        if self._closed:
            return
        if success:
            pos, total = self.engine.get_position()
            self._preview_info.configure(text=f"{item.source_name} | {item.title} | {pos}/{total}")
            self._status_label.configure(text=f"Playing | Next in {self.engine.interval}s")
            self._load_preview(item)
            self._reset_countdown()
            self._update_like_button()
        else:
            self._status_label.configure(text=f"Failed to set wallpaper: {item.title}")

    def _load_preview(self, item: WallpaperItem):
        if self._closed:
            return
        url = item.thumbnail_url or item.url
        seq = self._apply_seq

        def _do():
            if self._closed or seq != self._apply_seq:
                return
            try:
                img = self.cache.download_thumb(url, max_size=PREVIEW_MAX, timeout=8)
                if img and seq == self._apply_seq and not self._closed:
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                    self.after(0, lambda: self._set_preview(photo))
            except Exception:
                pass

        threading.Thread(target=_do, daemon=True).start()

    def _set_preview(self, photo):
        if self._closed:
            return
        self._preview_label.configure(image=photo, text="")
        old = self._preview_image
        self._preview_image = photo
        del old

    def _on_prev(self):
        item = self.engine.previous()
        if item:
            self._apply_wallpaper(item)

    def _on_next(self):
        item = self.engine.next()
        if item:
            self._apply_wallpaper(item)

    def _on_toggle_play(self):
        self.engine.toggle()
        if self.engine.playing:
            self._play_btn.configure(text="||")
            self._start_countdown()
        else:
            self._play_btn.configure(text=">")
            self._stop_countdown()

    def _on_shuffle(self):
        self.engine.reshuffle()
        self.config.set("shuffle", self.engine.shuffle)
        item = self.engine.get_current()
        if item:
            self._apply_wallpaper(item)

    def _on_interval_change(self, value):
        interval = int(value)
        self.engine.interval = interval
        self._interval_label.configure(text=f"{interval}s")
        if self._interval_after_id:
            self.after_cancel(self._interval_after_id)
        self._interval_after_id = self.after(500, lambda: self._save_interval(interval))

    def _save_interval(self, interval):
        self.config.set("interval", interval)
        self._interval_after_id = None

    def _on_style_change(self, style: str):
        self.config.set("style", style)
        if self._current_item:
            path = self.cache.get_cache_path(self._current_item.url)
            if path.exists():
                set_wallpaper(str(path), style)

    def _on_autostart_toggle(self):
        set_autostart(self._autostart_var.get())
        self.config.set("auto_start", self._autostart_var.get())

    def _start_countdown(self):
        self._stop_countdown()
        self._seconds_left = self.engine.interval
        self._tick_countdown()

    def _stop_countdown(self):
        if self._countdown_id:
            self.after_cancel(self._countdown_id)
            self._countdown_id = None

    def _reset_countdown(self):
        self._seconds_left = self.engine.interval

    def _tick_countdown(self):
        if self._closed or not self.engine.playing:
            return
        if self._seconds_left > 0:
            self._status_label.configure(text=f"Playing | Next in {self._seconds_left}s")
            self._seconds_left -= 1
            self._countdown_id = self.after(1000, self._tick_countdown)

    def _start_tray(self):
        if self._closed:
            return
        from ui.tray import TrayIcon
        self._tray_icon = TrayIcon(self)
        self._tray_icon.start()

    def _on_close(self):
        self._closed = True
        self._stop_countdown()
        if self._interval_after_id:
            self.after_cancel(self._interval_after_id)
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self.withdraw()

    def _force_quit(self):
        self._closed = True
        self.engine.stop()
        self._stop_countdown()
        if self._tray_icon:
            self._tray_icon.stop()
        self.cache.clear()
        self.destroy()

    def _open_add_source_dialog(self):
        from ui.add_source_dialog import AddSourceDialog
        dialog = AddSourceDialog(self, self.registry, self.config, self._on_sources_changed)
        dialog.grab_set()

    def _on_sources_changed(self):
        self._refresh_sources()
        self._fetch_and_load()

    # --- Favorites ---

    def _update_like_button(self):
        if not self._current_item:
            self._like_btn.configure(text="Like", fg_color=("gray75", "gray25"))
            return
        if self.favorites.is_liked(self._current_item.url):
            self._like_btn.configure(text="Liked", fg_color="#cc3333")
        else:
            self._like_btn.configure(text="Like", fg_color=("gray75", "gray25"))

    def _on_toggle_like(self):
        if not self._current_item:
            return
        liked = self.favorites.toggle_like(self._current_item)
        count = self.favorites.get_count()
        self._tab_fav_btn.configure(text=f"Favorites ({count})")
        self._fav_title_label.configure(text=f"Your Favorites ({count})")
        self._update_like_button()
        self._status_label.configure(text=f"{'Added to' if liked else 'Removed from'} favorites")

    def _refresh_favorites_list(self):
        for row in self._fav_rows:
            row.destroy()
        self._fav_rows.clear()

        items = self.favorites.get_liked()
        if not items:
            lbl = ctk.CTkLabel(
                self._fav_list_frame,
                text="No favorites yet.\nBrowse wallpapers and click Like to add them here.",
                text_color="gray", font=ctk.CTkFont(size=13),
            )
            lbl.grid(row=0, column=0, pady=40)
            self._fav_rows.append(lbl)
            return

        self._fav_selected_url = None
        for i, item in enumerate(items):
            row = ctk.CTkFrame(self._fav_list_frame)
            row.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            row.grid_columnconfigure(1, weight=1)

            btn = ctk.CTkButton(
                row, text=item.title, anchor="w", width=200,
                fg_color="transparent", hover_color=("gray70", "gray30"),
                command=lambda it=item: self._on_fav_item_click(it),
            )
            btn.grid(row=0, column=0, sticky="w", padx=5, pady=3)

            info = ctk.CTkLabel(
                row, text=f"{item.source_name} | {item.resolution or '?'}",
                font=ctk.CTkFont(size=10), text_color="gray",
            )
            info.grid(row=0, column=1, sticky="w", padx=5)

            play_btn = ctk.CTkButton(
                row, text="Play", width=50, height=24,
                command=lambda it=item: self._on_play_fav_item(it),
            )
            play_btn.grid(row=0, column=2, padx=5, pady=3)

            self._fav_rows.append(row)

    def _on_fav_item_click(self, item: WallpaperItem):
        self._fav_selected_url = item.url
        url = item.thumbnail_url or item.url

        def _do():
            try:
                img = self.cache.download_thumb(url, max_size=FAV_PREVIEW_MAX, timeout=8)
                if img and not self._closed:
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                    self.after(0, lambda: self._set_fav_preview(photo, item))
            except Exception:
                if not self._closed:
                    self.after(0, lambda: self._fav_preview_info.configure(
                        text=f"Could not load preview for {item.title}"
                    ))

        self._fav_preview_info.configure(text=f"Loading: {item.title}...")
        threading.Thread(target=_do, daemon=True).start()

    def _set_fav_preview(self, photo, item: WallpaperItem):
        if self._closed:
            return
        self._fav_preview_label.configure(image=photo, text="")
        old = self._fav_preview_image
        self._fav_preview_image = photo
        del old
        self._fav_preview_info.configure(
            text=f"{item.title} | {item.source_name} | {item.resolution or 'Unknown'}"
        )

    def _on_play_fav_item(self, item: WallpaperItem):
        self._apply_wallpaper(item)
        self._show_tab("browse")

    def _on_play_favorites(self):
        items = self.favorites.get_liked()
        if not items:
            self._status_label.configure(text="No favorites to play")
            return
        self.engine.set_playlist(items)
        self.engine.start()
        self._play_btn.configure(text="||")
        self._start_countdown()
        item = self.engine.get_current()
        if item:
            self._apply_wallpaper(item)
        self._show_tab("browse")
        self._status_label.configure(text=f"Playing {len(items)} favorites")

    def _on_remove_selected_fav(self):
        if not self._fav_selected_url:
            self._status_label.configure(text="Select a favorite first")
            return
        for item in self.favorites.get_liked():
            if item.url == self._fav_selected_url:
                self.favorites.toggle_like(item)
                break
        count = self.favorites.get_count()
        self._tab_fav_btn.configure(text=f"Favorites ({count})")
        self._fav_title_label.configure(text=f"Your Favorites ({count})")
        self._fav_selected_url = None
        self._fav_preview_label.configure(image=None, text="Select a favorite to preview")
        self._fav_preview_info.configure(text="")
        self._refresh_favorites_list()
        self._update_like_button()

    def _check_favorites_availability(self):
        if not self._closed:
            self.favorites.check_availability(on_complete=self._on_availability_checked)

    def _on_check_fav_availability(self):
        self._status_label.configure(text="Checking favorites availability...")
        self.favorites.check_availability(on_complete=self._on_availability_checked)

    def _on_availability_checked(self, removed_count, remaining):
        if self._closed:
            return
        if removed_count > 0:
            self._status_label.configure(
                text=f"Removed {removed_count} unavailable favorite(s). {len(remaining)} still available."
            )
        elif remaining:
            self._status_label.configure(text=f"All {len(remaining)} favorites available.")
        count = self.favorites.get_count()
        self._tab_fav_btn.configure(text=f"Favorites ({count})")
        self._fav_title_label.configure(text=f"Your Favorites ({count})")
        self._update_like_button()
        if self._active_tab == "favorites":
            self._refresh_favorites_list()
