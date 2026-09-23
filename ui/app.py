import threading
import customtkinter as ctk

from sources.registry import SourceRegistry
from sources.base import WallpaperItem
from core.cache import CacheManager
from core.config import Config
from core.slideshow import SlideshowEngine
from core.favorites import FavoritesManager
from core.wallpaper import set_wallpaper, get_screen_resolution
from core.autostart import is_autostart_enabled, set_autostart

PREVIEW_MAX = (450, 350)
FAV_PREVIEW_MAX = (500, 280)

PAD = 8
BTN_H = 32


class ArchImgApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config = Config()
        self.registry = SourceRegistry(config=self.config)
        self.cache = CacheManager(max_size_mb=self.config.get("max_cache_mb", 500))
        self.favorites = FavoritesManager()
        self.engine = SlideshowEngine(on_change_callback=self._on_wallpaper_change)

        screen_w, screen_h = get_screen_resolution()
        win_w = max(820, int(screen_w * 0.58))
        win_h = max(620, int(screen_h * 0.75))

        self.title("Wallpaper Engine")
        self.geometry(f"{win_w}x{win_h}")
        self.minsize(740, 540)

        ctk.set_appearance_mode(self.config.get("theme", "dark"))
        ctk.set_default_color_theme("blue")

        self._current_item: WallpaperItem | None = None
        self._preview_image = None
        self._fav_preview_image = None
        self._seconds_left = 0
        self._countdown_id = None
        self._active_tab = "browse"
        self._apply_seq = 0
        self._interval_after_id = None
        self._closed = False
        self._fav_selected_url = None
        self._history: list[WallpaperItem] = []
        self._history_index = -1
        self._tray_icon = None
        self._fetch_seq = 0
        self._source_health: dict[str, bool | None] = {}
        self._fav_rows: list[ctk.CTkFrame] = []
        self._fav_preview_seq = 0

        self._build_ui()
        self._load_settings()
        self._refresh_sources()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-q>", lambda e: self._force_quit())
        self.bind("<space>", lambda e: self._on_next() if self.focus_get() != self._search_entry else None)
        self.bind("<Right>", lambda e: self._on_next() if self.focus_get() != self._search_entry else None)
        self.bind("<Left>", lambda e: self._on_prev() if self.focus_get() != self._search_entry else None)
        self.bind("<Return>", lambda e: self._on_search() if self.focus_get() != self._search_entry else None)
        self.after(200, self._start_tray)
        self.after(800, self._check_source_health)
        self.after(1200, self._check_favorites_availability)

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

    # ─── Tab Bar ───────────────────────────────────────────────────────────

    def _build_tab_bar(self):
        bar = ctk.CTkFrame(self, height=48, corner_radius=0, fg_color=("gray88", "gray13"))
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(2, weight=1)

        self._tab_browse_btn = ctk.CTkButton(
            bar, text="  Browse  ", width=110, height=34, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#2196F3", "#1976D2"),
            hover_color=("#1E88E5", "#1565C0"),
            command=lambda: self._show_tab("browse"),
        )
        self._tab_browse_btn.grid(row=0, column=0, padx=(12, 4), pady=7)

        fav_count = self.favorites.get_count()
        self._tab_fav_btn = ctk.CTkButton(
            bar, text=f"  Favorites ({fav_count})  ", width=160, height=34, corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=lambda: self._show_tab("favorites"),
        )
        self._tab_fav_btn.grid(row=0, column=1, padx=4, pady=7)

        self._like_btn = ctk.CTkButton(
            bar, text="Like", width=80, height=34, corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color=("gray70", "gray30"),
            hover_color=("#E53935", "#C62828"),
            command=self._on_toggle_like,
        )
        self._like_btn.grid(row=0, column=3, padx=(0, 12), pady=7)

    def _show_tab(self, tab: str):
        self._active_tab = tab
        if tab == "browse":
            self._hide_fav_frame()
            self._browse_frame.grid(row=1, column=0, padx=PAD, pady=(PAD, 0), sticky="nsew")
            self._tab_browse_btn.configure(fg_color=("#2196F3", "#1976D2"))
            self._tab_fav_btn.configure(fg_color=("gray70", "gray30"))
        else:
            self._hide_browse_frame()
            self._fav_frame.grid(row=1, column=0, padx=PAD, pady=(PAD, 0), sticky="nsew")
            self._tab_browse_btn.configure(fg_color=("gray70", "gray30"))
            self._tab_fav_btn.configure(fg_color=("#2196F3", "#1976D2"))
            self._refresh_favorites_list()

    def _hide_fav_frame(self):
        if not self._closed:
            try:
                self._fav_frame.grid_forget()
            except Exception:
                pass

    def _hide_browse_frame(self):
        if not self._closed:
            try:
                self._browse_frame.grid_forget()
            except Exception:
                pass

    # ─── Browse Tab ────────────────────────────────────────────────────────

    def _build_browse_tab(self):
        self._browse_frame = ctk.CTkFrame(self, corner_radius=10)
        self._browse_frame.grid_columnconfigure(0, weight=1)
        self._browse_frame.grid_rowconfigure(2, weight=1)

        self._build_source_panel()
        self._build_search_panel()
        self._build_preview_panel()

    def _build_source_panel(self):
        frame = ctk.CTkFrame(self._browse_frame, corner_radius=8)
        frame.grid(row=0, column=0, padx=PAD, pady=(PAD, 4), sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        lbl = ctk.CTkLabel(frame, text="Sources", font=ctk.CTkFont(size=12, weight="bold"))
        lbl.grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")

        self._source_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._source_frame.grid(row=0, column=1, sticky="ew", pady=8)
        self._source_checkboxes: dict[str, tuple[ctk.CTkCheckBox, ctk.BooleanVar]] = {}

        right = ctk.CTkFrame(frame, fg_color="transparent")
        right.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        self._add_source_btn = ctk.CTkButton(
            right, text="+ Add Source", width=100, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=("#4CAF50", "#388E3C"),
            hover_color=("#43A047", "#2E7D32"),
            command=self._open_add_source_dialog,
        )
        self._add_source_btn.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(right, text="Mode:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(8, 4))
        self._mode_var = ctk.StringVar(value=self.config.get("playlist_mode", "merged"))
        self._mode_menu = ctk.CTkOptionMenu(
            right, variable=self._mode_var,
            values=["merged", "single"], width=90, height=BTN_H,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._on_mode_change,
        )
        self._mode_menu.pack(side="left", padx=(0, 4))

        self._single_source_var = ctk.StringVar(value="ArchImg")
        self._single_source_menu = ctk.CTkOptionMenu(
            right, variable=self._single_source_var,
            values=["ArchImg"], width=110, height=BTN_H,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._on_single_source_change,
        )

    def _build_search_panel(self):
        frame = ctk.CTkFrame(self._browse_frame, corner_radius=8)
        frame.grid(row=1, column=0, padx=PAD, pady=4, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Search", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=(12, 8), pady=8, sticky="w"
        )

        self._search_entry = ctk.CTkEntry(
            frame, placeholder_text="nature, cyberpunk, linux...", height=BTN_H,
            font=ctk.CTkFont(size=12),
        )
        self._search_entry.grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        self._search_entry.bind("<Return>", lambda e: self._on_search())

        self._search_btn = ctk.CTkButton(
            frame, text="Search", width=80, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=12),
            command=self._on_search,
        )
        self._search_btn.grid(row=0, column=2, padx=4, pady=8)

        ctk.CTkLabel(frame, text="Category", font=ctk.CTkFont(size=12)).grid(
            row=0, column=3, padx=(12, 4), pady=8, sticky="w"
        )
        self._category_var = ctk.StringVar(value="All")
        self._category_menu = ctk.CTkOptionMenu(
            frame, variable=self._category_var, values=["All"], width=110,
            height=BTN_H, font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._on_category_change,
        )
        self._category_menu.grid(row=0, column=4, padx=(4, 12), pady=8)

    def _build_preview_panel(self):
        self._preview_frame = ctk.CTkFrame(self._browse_frame, corner_radius=8)
        self._preview_frame.grid(row=2, column=0, padx=PAD, pady=(4, PAD), sticky="nsew")
        self._preview_frame.grid_rowconfigure(0, weight=1)
        self._preview_frame.grid_columnconfigure(0, weight=1)

        self._preview_label = ctk.CTkLabel(
            self._preview_frame, text="Press Refresh to load wallpapers",
            font=ctk.CTkFont(size=13), text_color="gray50",
        )
        self._preview_label.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")

        self._preview_info = ctk.CTkLabel(
            self._preview_frame, text="",
            font=ctk.CTkFont(size=11), text_color="gray60",
        )
        self._preview_info.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="s")

    # ─── Controls Panel ────────────────────────────────────────────────────

    def _build_controls_panel(self):
        frame = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=("gray88", "gray13"))
        frame.grid(row=2, column=0, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        # Transport buttons
        transport = ctk.CTkFrame(frame, fg_color="transparent")
        transport.grid(row=0, column=0, padx=(PAD, 0), pady=PAD, sticky="w")

        btn_style = dict(width=44, height=BTN_H, corner_radius=8, font=ctk.CTkFont(size=14))

        self._prev_btn = ctk.CTkButton(
            transport, text="\u25C0", **btn_style,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=self._on_prev,
        )
        self._prev_btn.pack(side="left", padx=3)

        self._play_btn = ctk.CTkButton(
            transport, text="\u23F8", **btn_style,
            fg_color=("#2196F3", "#1976D2"), hover_color=("#1E88E5", "#1565C0"),
            command=self._on_toggle_play,
        )
        self._play_btn.pack(side="left", padx=3)

        self._next_btn = ctk.CTkButton(
            transport, text="\u25B6", **btn_style,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=self._on_next,
        )
        self._next_btn.pack(side="left", padx=3)

        sep = ctk.CTkLabel(transport, text="|", text_color="gray50", width=12)
        sep.pack(side="left", padx=6)

        ctk.CTkButton(
            transport, text="Shuffle", width=72, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=self._on_shuffle,
        ).pack(side="left", padx=3)

        self._refresh_btn = ctk.CTkButton(
            transport, text="Refresh", width=72, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=("#4CAF50", "#388E3C"), hover_color=("#43A047", "#2E7D32"),
            command=self._refresh_sources,
        )
        self._refresh_btn.pack(side="left", padx=3)

        # Settings
        settings = ctk.CTkFrame(frame, fg_color="transparent")
        settings.grid(row=0, column=1, padx=(0, PAD), pady=PAD, sticky="e")

        ctk.CTkLabel(settings, text="Interval:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 4))
        self._interval_slider = ctk.CTkSlider(
            settings, from_=5, to=300, number_of_steps=59, width=130, height=16,
            command=self._on_interval_change,
        )
        self._interval_slider.set(self.config.get("interval", 30))
        self._interval_slider.pack(side="left", padx=(0, 4))

        self._interval_label = ctk.CTkLabel(
            settings, text=f"{self.config.get('interval', 30)}s",
            width=36, font=ctk.CTkFont(size=11),
        )
        self._interval_label.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(settings, text="Style:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 4))
        self._style_var = ctk.StringVar(value=self.config.get("style", "Fill"))
        self._style_menu = ctk.CTkOptionMenu(
            settings, variable=self._style_var,
            values=["Fill", "Fit", "Stretch", "Tile", "Center", "Span"],
            width=80, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=11),
            command=self._on_style_change,
        )
        self._style_menu.pack(side="left", padx=(0, 10))

        self._autostart_var = ctk.BooleanVar(value=self.config.get("auto_start", False))
        self._autostart_cb = ctk.CTkCheckBox(
            settings, text="Auto-start", variable=self._autostart_var,
            font=ctk.CTkFont(size=11),
            command=self._on_autostart_toggle,
        )
        self._autostart_cb.pack(side="left", padx=(4, 0))

    # ─── Status Bar ────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=("gray88", "gray13"))
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self._status_label = ctk.CTkLabel(
            bar, text="Ready",
            font=ctk.CTkFont(size=11), text_color="gray50", anchor="w",
        )
        self._status_label.grid(row=0, column=0, padx=12, pady=4, sticky="ew")

        hint = ctk.CTkLabel(
            bar, text="Space=Next  \u2190\u2192=Navigate  Enter=Search",
            font=ctk.CTkFont(size=10), text_color="gray40", anchor="e",
        )
        hint.grid(row=0, column=1, padx=12, pady=4, sticky="e")

    # ─── Favorites Tab ─────────────────────────────────────────────────────

    def _build_favorites_tab(self):
        self._fav_frame = ctk.CTkFrame(self, corner_radius=10)
        self._fav_frame.grid_columnconfigure(0, weight=1)
        self._fav_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self._fav_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 4))
        header.grid_columnconfigure(1, weight=1)

        self._fav_title_label = ctk.CTkLabel(
            header, text=f"Your Favorites ({self.favorites.get_count()})",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._fav_title_label.grid(row=0, column=0, sticky="w", padx=(4, 0))

        ctk.CTkButton(
            header, text="Check Availability", width=150, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=self._on_check_fav_availability,
        ).grid(row=0, column=1, sticky="e")

        self._fav_list_frame = ctk.CTkScrollableFrame(
            self._fav_frame, corner_radius=8,
            scrollbar_button_color="gray40", scrollbar_button_hover_color="gray50",
        )
        self._fav_list_frame.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=4)
        self._fav_list_frame.grid_columnconfigure(0, weight=1)

        self._fav_preview_frame = ctk.CTkFrame(self._fav_frame, height=160, corner_radius=8)
        self._fav_preview_frame.grid(row=2, column=0, sticky="ew", padx=PAD, pady=(0, 4))
        self._fav_preview_frame.grid_columnconfigure(0, weight=1)

        self._fav_preview_label = ctk.CTkLabel(
            self._fav_preview_frame, text="Select a favorite to preview",
            text_color="gray50", font=ctk.CTkFont(size=12),
        )
        self._fav_preview_label.grid(row=0, column=0, padx=12, pady=8, sticky="nsew")

        self._fav_preview_info = ctk.CTkLabel(
            self._fav_preview_frame, text="",
            font=ctk.CTkFont(size=10), text_color="gray50",
        )
        self._fav_preview_info.grid(row=1, column=0, padx=12, pady=(0, 8))

        fav_btn_frame = ctk.CTkFrame(self._fav_frame, fg_color="transparent")
        fav_btn_frame.grid(row=3, column=0, sticky="ew", padx=PAD, pady=(0, PAD))

        ctk.CTkButton(
            fav_btn_frame, text="Play Favorites", width=130, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=12),
            fg_color=("#2196F3", "#1976D2"), hover_color=("#1E88E5", "#1565C0"),
            command=self._on_play_favorites,
        ).pack(side="left", padx=(4, 0))

        ctk.CTkButton(
            fav_btn_frame, text="Remove Selected", width=130, height=BTN_H, corner_radius=6,
            font=ctk.CTkFont(size=12),
            fg_color=("#E53935", "#C62828"), hover_color=("#D32F2F", "#B71C1C"),
            command=self._on_remove_selected_fav,
        ).pack(side="right", padx=(0, 4))

    # ─── Settings ──────────────────────────────────────────────────────────

    def _load_settings(self):
        self._interval_slider.set(self.config.get("interval", 30))
        self._interval_label.configure(text=f"{self.config.get('interval', 30)}s")
        self.engine.interval = self.config.get("interval", 30)
        self.engine.shuffle = self.config.get("shuffle", True)
        if is_autostart_enabled():
            self._autostart_var.set(True)
        if self.config.get("playlist_mode") == "single":
            self._single_source_menu.pack(side="left", padx=(4, 0))
        wh = self.registry.get("Wallhaven")
        if wh:
            wh.api_key = self.config.get("wallhaven_api_key", "")
            wh.min_resolution = self.config.get("wallhaven_min_resolution", "1920x1080")

    # ─── Source Management ─────────────────────────────────────────────────

    def _check_source_health(self):
        if self._closed:
            return

        def _do():
            for name, src in self.registry.get_all().items():
                try:
                    available = src.is_available()
                except Exception:
                    available = False
                self._source_health[name] = available
            if not self._closed:
                self.after(0, self._update_source_health_ui)

        threading.Thread(target=_do, daemon=True).start()

    def _update_source_health_ui(self):
        if self._closed:
            return
        enabled = self.config.get("enabled_sources", [])
        unhealthy = [n for n in enabled if self._source_health.get(n) is False]
        if unhealthy:
            self._status_label.configure(
                text=f"Warning: {', '.join(unhealthy)} appear(s) offline",
                text_color="#FF9800",
            )

    def _refresh_sources(self):
        old_children = list(self._source_frame.winfo_children())
        self._source_checkboxes.clear()

        def _rebuild():
            if self._closed:
                return
            for w in old_children:
                try:
                    w.pack_forget()
                    w.destroy()
                except Exception:
                    pass

            enabled = self.config.get("enabled_sources", ["ArchImg", "Wallhaven"])
            for name in self.registry.get_all():
                var = ctk.BooleanVar(value=name in enabled)
                health = self._source_health.get(name)
                prefix = ""
                color = None
                if health is True:
                    prefix = "\u2714 "
                    color = "#4CAF50"
                elif health is False:
                    prefix = "\u2716 "
                    color = "#F44336"

                cb = ctk.CTkCheckBox(
                    self._source_frame, text=prefix + name, variable=var,
                    font=ctk.CTkFont(size=11),
                    command=lambda n=name, v=var: self._on_source_toggle(n, v.get()),
                )
                if self.registry.is_custom(name):
                    cb.bind("<Button-3>", lambda e, n=name: self._show_source_context_menu(e, n))
                if color:
                    cb.configure(text_color=color)
                cb.pack(side="left", padx=(0, 10))
                self._source_checkboxes[name] = (cb, var)

            self._update_single_source_menu()
            self._update_categories()

        self.after_idle(_rebuild)

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
        current = list(self.config.get("enabled_sources", []))
        if enabled and name not in current:
            current.append(name)
        elif not enabled and name in current:
            current.remove(name)
        self.config.set("enabled_sources", current)
        self._update_single_source_menu()
        self._update_categories()

    def _show_source_context_menu(self, event, name: str):
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=f"Remove {name}",
            command=lambda: self._on_remove_source(name),
        )
        menu.tk_popup(event.x_root, event.y_root)
        menu.bind("<FocusOut>", lambda e: menu.destroy())
        menu.focus_set()

    def _on_remove_source(self, name: str):
        self.registry.remove(name)
        current = list(self.config.get("enabled_sources", []))
        if name in current:
            current.remove(name)
            self.config.set("enabled_sources", current)
        self._refresh_sources()
        self._check_source_health()
        self._status_label.configure(text=f"Removed source: {name}", text_color="#4CAF50")

    def _on_mode_change(self, mode: str):
        self.config.set("playlist_mode", mode)
        if mode == "single":
            self._single_source_menu.pack(side="left", padx=(4, 0))
        else:
            self._single_source_menu.pack_forget()

    def _on_single_source_change(self, source: str):
        self.config.set("active_source", source)
        if self.config.get("playlist_mode") == "single":
            self._fetch_and_load(source=source)

    def _on_search(self):
        query = self._search_entry.get().strip() or None
        self._fetch_and_load(query=query)

    def _on_category_change(self, category: str):
        self._fetch_and_load(category=category if category != "All" else None)

    # ─── Fetch & Load ──────────────────────────────────────────────────────

    def _fetch_and_load(self, query=None, category=None, source=None):
        if self._closed:
            return
        self._fetch_seq += 1
        seq = self._fetch_seq
        self._refresh_btn.configure(state="disabled", text="Loading...")
        self._status_label.configure(text="Fetching wallpapers...", text_color="gray50")

        def _do():
            mode = self.config.get("playlist_mode", "merged")
            if mode == "single" or source:
                src_name = source or self._single_source_var.get()
                items = self.registry.fetch_source(src_name, query=query, category=category, limit=100)
            else:
                enabled = self.config.get("enabled_sources", [])
                items = self.registry.fetch_all(enabled, query=query, category=category, limit_per_source=50)
            if not self._closed and seq == self._fetch_seq:
                self.after(0, lambda: self._on_fetch_complete(items))

        threading.Thread(target=_do, daemon=True).start()

    def _on_fetch_complete(self, items: list[WallpaperItem]):
        if self._closed:
            return
        self._refresh_btn.configure(state="normal", text="Refresh")

        if not items:
            self._status_label.configure(
                text="No wallpapers found. Try different search or check source settings.",
                text_color="#FF9800",
            )
            return

        self.engine.set_playlist(items)
        src_count = len(set(i.source_name for i in items))
        self._status_label.configure(
            text=f"Loaded {len(items)} wallpapers from {src_count} source(s)",
            text_color="#4CAF50",
        )

        if not self.engine.playing:
            self.engine.start()
            self._play_btn.configure(text="\u23F8")
            self._start_countdown()

        item = self.engine.get_current()
        if item:
            self._apply_wallpaper(item)

    # ─── Wallpaper Engine ──────────────────────────────────────────────────

    def _on_wallpaper_change(self, item: WallpaperItem):
        if not self._closed:
            self.after(0, lambda: self._apply_wallpaper(item))

    def _apply_wallpaper(self, item: WallpaperItem):
        if self._closed:
            return
        self._current_item = item
        self._apply_seq += 1
        seq = self._apply_seq
        self._status_label.configure(text=f"Loading: {item.title}...", text_color="gray50")

        def _do():
            path = self.cache.download(item.url)
            if path and seq == self._apply_seq and not self._closed:
                style = self.config.get("style", "Fill")
                success, err = set_wallpaper(str(path), style)
                if not self._closed:
                    self.after(0, lambda: self._on_wallpaper_set(item, success, err))
            elif not self._closed and seq == self._apply_seq:
                self.after(0, lambda: self._status_label.configure(
                    text=f"Failed to download: {item.title}", text_color="#F44336"
                ))

        threading.Thread(target=_do, daemon=True).start()

    def _on_wallpaper_set(self, item: WallpaperItem, success: bool, err: str = ""):
        if self._closed:
            return
        if success:
            pos, total = self.engine.get_position()
            self._preview_info.configure(
                text=f"{item.source_name}  \u2022  {item.title}  \u2022  {pos}/{total}"
            )
            self._status_label.configure(
                text=f"Playing  \u2022  Next in {self.engine.interval}s",
                text_color="#4CAF50",
            )
            self._load_preview(item)
            self._update_like_button()

            if self.engine.playing:
                self._start_countdown()

            if item not in self._history:
                self._history.append(item)
                if len(self._history) > 200:
                    self._history = self._history[-200:]
                self._history_index = len(self._history) - 1
            else:
                self._history_index = self._history.index(item)
        else:
            self._status_label.configure(
                text=f"Failed: {item.title} ({err})", text_color="#F44336"
            )

    def _load_preview(self, item: WallpaperItem):
        if self._closed:
            return
        url = item.thumbnail_url or item.url
        seq = self._apply_seq

        def _do():
            if self._closed or seq != self._apply_seq:
                return
            try:
                img = self.cache.download_thumb(url, max_size=PREVIEW_MAX, timeout=10)
                if img:
                    if seq == self._apply_seq and not self._closed:
                        photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                        self.after(0, lambda: self._set_preview(photo))
                    else:
                        img.close()
            except Exception:
                pass

        threading.Thread(target=_do, daemon=True).start()

    def _set_preview(self, photo):
        if self._closed:
            return
        old = self._preview_image
        self._preview_image = photo
        self._preview_label.configure(image=photo, text="")
        if old:
            try:
                old.close()
            except Exception:
                pass

    # ─── Transport Controls ────────────────────────────────────────────────

    def _on_prev(self):
        if self._history and self._history_index > 0:
            self._history_index -= 1
            item = self._history[self._history_index]
            self._apply_wallpaper(item)
        else:
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
            self._play_btn.configure(text="\u23F8")
            self._start_countdown()
        else:
            self._play_btn.configure(text="\u25B6")
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
                def _do():
                    success, err = set_wallpaper(str(path), style)
                    if not self._closed:
                        if not success:
                            self.after(0, lambda: self._status_label.configure(
                                text=f"Style change failed: {err}", text_color="#F44336"
                            ))
                threading.Thread(target=_do, daemon=True).start()

    def _on_autostart_toggle(self):
        set_autostart(self._autostart_var.get())
        self.config.set("auto_start", self._autostart_var.get())

    # ─── Countdown ─────────────────────────────────────────────────────────

    def _start_countdown(self):
        self._stop_countdown()
        self._seconds_left = self.engine.interval
        self._tick_countdown()

    def _stop_countdown(self):
        if self._countdown_id:
            self.after_cancel(self._countdown_id)
            self._countdown_id = None

    def _tick_countdown(self):
        if self._closed or not self.engine.playing:
            return
        if self._seconds_left > 0:
            self._status_label.configure(
                text=f"Playing  \u2022  Next in {self._seconds_left}s",
                text_color="#4CAF50",
            )
            self._seconds_left -= 1
            self._countdown_id = self.after(1000, self._tick_countdown)

    # ─── Tray ──────────────────────────────────────────────────────────────

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
        self.withdraw()

    def _force_quit(self):
        self._closed = True
        self.engine.stop()
        self._stop_countdown()
        if self._tray_icon:
            self._tray_icon.stop()
        self.destroy()

    def _open_add_source_dialog(self):
        from ui.add_source_dialog import AddSourceDialog
        dialog = AddSourceDialog(self, self.registry, self.config, self._on_sources_changed)
        dialog.grab_set()

    def _on_sources_changed(self):
        self._refresh_sources()
        self._check_source_health()
        self._fetch_and_load()

    # ─── Favorites ─────────────────────────────────────────────────────────

    def _update_like_button(self):
        if not self._current_item:
            self._like_btn.configure(text="Like", fg_color=("gray70", "gray30"))
            return
        if self.favorites.is_liked(self._current_item.url):
            self._like_btn.configure(text="Liked", fg_color=("#E53935", "#C62828"))
        else:
            self._like_btn.configure(text="Like", fg_color=("gray70", "gray30"))

    def _on_toggle_like(self):
        if not self._current_item:
            return
        liked = self.favorites.toggle_like(self._current_item)
        count = self.favorites.get_count()
        self._tab_fav_btn.configure(text=f"  Favorites ({count})  ")
        self._fav_title_label.configure(text=f"Your Favorites ({count})")
        self._update_like_button()
        self._status_label.configure(
            text=f"{'Added to' if liked else 'Removed from'} favorites",
            text_color="#4CAF50" if liked else "gray50",
        )

    def _refresh_favorites_list(self):
        if self._closed:
            return
        old_rows = list(self._fav_rows)
        self._fav_rows.clear()

        def _rebuild():
            if self._closed:
                return
            for row in old_rows:
                try:
                    row.grid_forget()
                    row.destroy()
                except Exception:
                    pass

            items = self.favorites.get_liked()
            if not items:
                lbl = ctk.CTkLabel(
                    self._fav_list_frame,
                    text="No favorites yet.\nBrowse wallpapers and click Like to add them here.",
                    text_color="gray50", font=ctk.CTkFont(size=13),
                )
                lbl.grid(row=0, column=0, pady=50, padx=20)
                self._fav_rows.append(lbl)
                return

            self._fav_selected_url = None
            for i, item in enumerate(items):
                row = ctk.CTkFrame(self._fav_list_frame, corner_radius=6)
                row.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
                row.grid_columnconfigure(1, weight=1)

                title_btn = ctk.CTkButton(
                    row, text=item.title, anchor="w", width=220, height=28,
                    font=ctk.CTkFont(size=11),
                    fg_color="transparent", hover_color=("gray75", "gray25"),
                    text_color="white",
                    command=lambda it=item: self._on_fav_item_click(it),
                )
                title_btn.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=4)

                info = ctk.CTkLabel(
                    row, text=f"{item.source_name}  \u2022  {item.resolution or '?'}",
                    font=ctk.CTkFont(size=10), text_color="gray50",
                )
                info.grid(row=0, column=1, sticky="w", padx=4)

                play_btn = ctk.CTkButton(
                    row, text="Play", width=52, height=26, corner_radius=6,
                    font=ctk.CTkFont(size=10),
                    fg_color=("#2196F3", "#1976D2"), hover_color=("#1E88E5", "#1565C0"),
                    command=lambda it=item: self._on_play_fav_item(it),
                )
                play_btn.grid(row=0, column=2, padx=(4, 8), pady=4)

                self._fav_rows.append(row)

        self.after_idle(_rebuild)

    def _on_fav_item_click(self, item: WallpaperItem):
        self._fav_selected_url = item.url
        self._fav_preview_seq += 1
        seq = self._fav_preview_seq
        url = item.thumbnail_url or item.url

        def _do():
            try:
                img = self.cache.download_thumb(url, max_size=FAV_PREVIEW_MAX, timeout=10)
                if img:
                    if seq == self._fav_preview_seq and not self._closed:
                        photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                        self.after(0, lambda: self._set_fav_preview(photo, item))
                    else:
                        img.close()
            except Exception:
                if seq == self._fav_preview_seq and not self._closed:
                    self.after(0, lambda: self._fav_preview_info.configure(
                        text=f"Could not load preview for {item.title}"
                    ))

        self._fav_preview_info.configure(text=f"Loading: {item.title}...")
        threading.Thread(target=_do, daemon=True).start()

    def _set_fav_preview(self, photo, item: WallpaperItem):
        if self._closed:
            return
        old = self._fav_preview_image
        self._fav_preview_image = photo
        self._fav_preview_label.configure(image=photo, text="")
        if old:
            try:
                old.close()
            except Exception:
                pass
        self._fav_preview_info.configure(
            text=f"{item.title}  \u2022  {item.source_name}  \u2022  {item.resolution or 'Unknown'}"
        )

    def _on_play_fav_item(self, item: WallpaperItem):
        self._apply_wallpaper(item)
        self._show_tab("browse")

    def _on_play_favorites(self):
        items = self.favorites.get_liked()
        if not items:
            self._status_label.configure(text="No favorites to play", text_color="#FF9800")
            return
        self.engine.set_playlist(items)
        self.engine.start()
        self._play_btn.configure(text="\u23F8")
        self._start_countdown()
        item = self.engine.get_current()
        if item:
            self._apply_wallpaper(item)
        self._show_tab("browse")
        self._status_label.configure(text=f"Playing {len(items)} favorites", text_color="#4CAF50")

    def _on_remove_selected_fav(self):
        if not self._fav_selected_url:
            self._status_label.configure(text="Select a favorite first", text_color="#FF9800")
            return
        for item in self.favorites.get_liked():
            if item.url == self._fav_selected_url:
                self.favorites.toggle_like(item)
                break
        count = self.favorites.get_count()
        self._tab_fav_btn.configure(text=f"  Favorites ({count})  ")
        self._fav_title_label.configure(text=f"Your Favorites ({count})")
        self._fav_selected_url = None
        self._fav_preview_label.configure(image=None, text="Select a favorite to preview")
        self._fav_preview_info.configure(text="")
        self._refresh_favorites_list()
        self._update_like_button()

    def _check_favorites_availability(self):
        if not self._closed:
            self.favorites.check_availability(
                on_complete=lambda r, rem: self.after(0, lambda: self._on_availability_checked(r, rem))
            )

    def _on_check_fav_availability(self):
        self._status_label.configure(text="Checking favorites availability...", text_color="gray50")
        self.favorites.check_availability(
            on_complete=lambda r, rem: self.after(0, lambda: self._on_availability_checked(r, rem))
        )

    def _on_availability_checked(self, removed_count, remaining):
        if self._closed:
            return
        if removed_count > 0:
            self._status_label.configure(
                text=f"Removed {removed_count} unavailable. {len(remaining)} still available.",
                text_color="#FF9800",
            )
        elif remaining:
            self._status_label.configure(
                text=f"All {len(remaining)} favorites available.",
                text_color="#4CAF50",
            )
        count = self.favorites.get_count()
        self._tab_fav_btn.configure(text=f"  Favorites ({count})  ")
        self._fav_title_label.configure(text=f"Your Favorites ({count})")
        self._update_like_button()
        if self._active_tab == "favorites":
            self._refresh_favorites_list()
