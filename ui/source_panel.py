import threading
import customtkinter as ctk
from sources.wallwidgy import WallwidgySource


class SourceSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, source_name, registry, config):
        super().__init__(parent)
        self.source_name = source_name
        self.registry = registry
        self.config = config
        self.source = registry.get(source_name)
        self._after_ids: list[str] = []

        self.title(f"{source_name} Settings")
        self.geometry("420x400")
        self.resizable(False, False)

        self.after(50, self._ensure_on_top)
        self._build_ui()

    def _ensure_on_top(self):
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        tid = self.after(300, lambda: self.attributes("-topmost", False))
        self._after_ids.append(tid)

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text=f"{self.source_name} Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(padx=20, pady=(15, 10))

        if self.source_name == "Wallhaven":
            self._build_wallhaven_settings()
        elif self.source_name == "Wallwidgy":
            self._build_wallwidgy_settings()
        elif self.source_name == "Openverse":
            self._build_openverse_settings()
        else:
            ctk.CTkLabel(
                self, text="No additional settings for this source."
            ).pack(padx=20, pady=20)

    def _build_wallhaven_settings(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(frame, text="Search query:").pack(anchor="w")
        self._query_entry = ctk.CTkEntry(
            frame, placeholder_text="nature, cyberpunk, linux...", width=350,
        )
        self._query_entry.pack(fill="x", pady=(0, 10))
        self._query_entry.insert(0, self.config.get("wallhaven_query", ""))

        ctk.CTkLabel(frame, text="Min resolution:").pack(anchor="w")
        self._res_var = ctk.StringVar(
            value=self.config.get("wallhaven_min_resolution", "1920x1080")
        )
        ctk.CTkOptionMenu(
            frame, variable=self._res_var,
            values=["1280x720", "1920x1080", "2560x1440", "3840x2160"],
            width=200,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(frame, text="API key (optional, for NSFW):").pack(anchor="w")
        self._api_key_entry = ctk.CTkEntry(
            frame, placeholder_text="API key...", width=350, show="*"
        )
        self._api_key_entry.pack(fill="x", pady=(0, 10))
        self._api_key_entry.insert(0, self.config.get("wallhaven_api_key", ""))

        ctk.CTkButton(frame, text="Save", command=self._save_wallhaven).pack(pady=10)

    def _build_wallwidgy_settings(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(frame, text="Category:").pack(anchor="w")
        saved_cat = self.config.get("wallwidgy_category", "all")
        self._cat_var = ctk.StringVar(value=saved_cat)
        ctk.CTkOptionMenu(
            frame, variable=self._cat_var,
            values=WallwidgySource.CATEGORIES, width=200,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(frame, text="Color:").pack(anchor="w")
        saved_color = self.config.get("wallwidgy_color", "all")
        self._color_var = ctk.StringVar(value=saved_color)
        ctk.CTkOptionMenu(
            frame, variable=self._color_var,
            values=WallwidgySource.COLORS, width=200,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkButton(frame, text="Save", command=self._save_wallwidgy).pack(pady=10)

    def _build_openverse_settings(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(frame, text="Search query:").pack(anchor="w")
        self._query_entry = ctk.CTkEntry(
            frame, placeholder_text="nature, landscape, sunset...", width=350,
        )
        self._query_entry.pack(fill="x", pady=(0, 10))
        self._query_entry.insert(0, self.config.get("openverse_query", "wallpaper nature landscape"))

        ctk.CTkButton(frame, text="Save", command=self._save_openverse).pack(pady=10)

    def _save_wallhaven(self):
        api_key = self._api_key_entry.get().strip()
        min_res = self._res_var.get()
        self.config.update({
            "wallhaven_query": self._query_entry.get().strip(),
            "wallhaven_min_resolution": min_res,
            "wallhaven_api_key": api_key,
        })
        src = self.registry.get("Wallhaven")
        if src:
            src.api_key = api_key
            src.min_resolution = min_res
        self.destroy()

    def _save_wallwidgy(self):
        cat = self._cat_var.get()
        color = self._color_var.get()
        self.config.update({
            "wallwidgy_category": cat,
            "wallwidgy_color": color,
        })
        src = self.registry.get("Wallwidgy")
        if src and isinstance(src, WallwidgySource):
            src.category = cat
            src.color = color
        self.destroy()

    def _save_openverse(self):
        self.config.set("openverse_query", self._query_entry.get().strip())
        self.destroy()

    def destroy(self):
        for tid in self._after_ids:
            try:
                self.after_cancel(tid)
            except Exception:
                pass
        self._after_ids.clear()
        super().destroy()
