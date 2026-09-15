import customtkinter as ctk


class SourceSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, source_name, registry, config):
        super().__init__(parent)
        self.source_name = source_name
        self.registry = registry
        self.config = config
        self.source = registry.get(source_name)

        self.title(f"{source_name} Settings")
        self.geometry("400x350")
        self.resizable(False, False)

        self._build_ui()

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
            frame,
            placeholder_text="nature, cyberpunk, linux...",
            width=350,
        )
        self._query_entry.pack(fill="x", pady=(0, 10))
        self._query_entry.insert(0, self.config.get("wallhaven_query", ""))

        ctk.CTkLabel(frame, text="Min resolution:").pack(anchor="w")
        self._res_var = ctk.StringVar(
            value=self.config.get("wallhaven_min_resolution", "1920x1080")
        )
        ctk.CTkOptionMenu(
            frame,
            variable=self._res_var,
            values=["1280x720", "1920x1080", "2560x1440", "3840x2160"],
            width=200,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(frame, text="API key (optional, for NSFW):").pack(anchor="w")
        self._api_key_entry = ctk.CTkEntry(frame, placeholder_text="API key...", width=350, show="*")
        self._api_key_entry.pack(fill="x", pady=(0, 10))
        self._api_key_entry.insert(0, self.config.get("wallhaven_api_key", ""))

        ctk.CTkButton(frame, text="Save", command=self._save_wallhaven).pack(pady=10)

    def _build_wallwidgy_settings(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(frame, text="Category:").pack(anchor="w")
        self._cat_var = ctk.StringVar(
            value=self.config.get("wallwidgy_category", "all")
        )
        ctk.CTkOptionMenu(
            frame,
            variable=self._cat_var,
            values=["all", "abstract", "anime", "architecture", "art", "cars", "minimal", "nature", "tech"],
            width=200,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(frame, text="Color:").pack(anchor="w")
        self._color_var = ctk.StringVar(
            value=self.config.get("wallwidgy_color", "all")
        )
        ctk.CTkOptionMenu(
            frame,
            variable=self._color_var,
            values=["all", "blue", "red", "green", "purple", "pink", "orange", "yellow", "black", "white"],
            width=200,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkButton(frame, text="Save", command=self._save_wallwidgy).pack(pady=10)

    def _build_openverse_settings(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(frame, text="Search query:").pack(anchor="w")
        self._query_entry = ctk.CTkEntry(
            frame,
            placeholder_text="nature, landscape, sunset...",
            width=350,
        )
        self._query_entry.pack(fill="x", pady=(0, 10))
        self._query_entry.insert(0, self.config.get("openverse_query", "wallpaper nature landscape"))

        ctk.CTkButton(frame, text="Save", command=self._save_openverse).pack(pady=10)

    def _save_wallhaven(self):
        self.config.update({
            "wallhaven_query": self._query_entry.get().strip(),
            "wallhaven_min_resolution": self._res_var.get(),
            "wallhaven_api_key": self._api_key_entry.get().strip(),
        })
        self.destroy()

    def _save_wallwidgy(self):
        self.config.update({
            "wallwidgy_category": self._cat_var.get(),
            "wallwidgy_color": self._color_var.get(),
        })
        self.destroy()

    def _save_openverse(self):
        self.config.set("openverse_query", self._query_entry.get().strip())
        self.destroy()
