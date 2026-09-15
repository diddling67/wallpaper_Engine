import threading
import customtkinter as ctk
from sources.custom import CustomSource
from sources.base import CompatibilityResult


class AddSourceDialog(ctk.CTkToplevel):
    def __init__(self, parent, registry, config, on_change_callback):
        super().__init__(parent)
        self.registry = registry
        self.config = config
        self._on_change = on_change_callback

        self.title("Add Custom Wallpaper Source")
        self.geometry("520x420")
        self.resizable(False, False)

        self._compatibility: CompatibilityResult | None = None
        self._custom_source: CustomSource | None = None
        self._probe_running = False
        self._after_ids: list[str] = []

        self._build_ui()
        self.after(50, self._ensure_on_top)

    def _ensure_on_top(self):
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="Add Custom Wallpaper Source",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(padx=20, pady=(15, 5))

        ctk.CTkLabel(
            self,
            text="Paste a wallpaper website URL. It will be scanned automatically.",
        ).pack(padx=20, pady=(0, 10))

        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(url_frame, text="URL:").pack(side="left", padx=(0, 5))
        self._url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://example.com/wallpapers",
            width=370,
        )
        self._url_entry.pack(side="left", fill="x", expand=True)
        self._url_entry.bind("<Return>", self._on_url_enter)

        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=(0, 5))

        ctk.CTkLabel(name_frame, text="Name:").pack(side="left", padx=(0, 5))
        self._name_entry = ctk.CTkEntry(
            name_frame,
            placeholder_text="(auto-detected if left empty)",
            width=370,
        )
        self._name_entry.pack(side="left", fill="x", expand=True)

        self._progress_frame = ctk.CTkFrame(self)
        self._progress_frame.pack(fill="x", padx=20, pady=5)

        self._progress_label = ctk.CTkLabel(
            self._progress_frame,
            text="Enter a URL above and press Enter to start scanning",
        )
        self._progress_label.pack(padx=15, pady=10, anchor="w")

        self._progress_bar = ctk.CTkProgressBar(self._progress_frame, width=460)
        self._progress_bar.pack(padx=15, pady=(0, 10))
        self._progress_bar.set(0)

        self._result_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._result_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self._add_btn = ctk.CTkButton(
            self._result_frame,
            text="Add Source",
            state="disabled",
            command=self._on_add,
        )
        self._add_btn.pack(pady=(0, 5))

        self._remove_btn = ctk.CTkButton(
            self._result_frame,
            text="Remove & Try Different URL",
            state="disabled",
            fg_color="#555555",
            command=self._on_remove_and_retry,
        )

        self._status_label = ctk.CTkLabel(
            self._result_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._status_label.pack(pady=2)

    def _on_url_enter(self, event=None):
        if self._probe_running:
            return
        self._start_auto_scan()

    def _start_auto_scan(self):
        url = self._url_entry.get().strip()
        if not url:
            return
        if self._probe_running:
            return

        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self._url_entry.delete(0, "end")
            self._url_entry.insert(0, url)

        self._probe_running = True
        self._add_btn.configure(state="disabled")
        self._remove_btn.pack_forget()

        name = self._name_entry.get().strip()
        if not name:
            try:
                name = url.split("//")[-1].split("/")[0].split("?")[0]
            except Exception:
                name = "Custom Source"

        self._progress_bar.set(0)
        self._progress_label.configure(text="Step 1/5: Connecting to website...")
        self._status_label.configure(text="Scanning...", text_color="gray")
        self.update_idletasks()

        self._run_scan_steps(url, name, 0)

    def _run_scan_steps(self, url, name, step):
        if self._probe_running is False:
            return
        steps = [
            ("Step 1/5: Connecting to website...", 0.1),
            ("Step 2/5: Checking for manifest files...", 0.3),
            ("Step 3/5: Probing API endpoints...", 0.5),
            ("Step 4/5: Scanning HTML for images...", 0.7),
            ("Step 5/5: Validating and testing downloads...", 0.9),
        ]
        if step < len(steps):
            msg, progress = steps[step]
            self._progress_label.configure(text=msg)
            self._progress_bar.set(progress)
            self.update_idletasks()
            tid = self.after(350, lambda: self._run_scan_steps(url, name, step + 1))
            self._after_ids.append(tid)
        else:
            self._do_probe(url, name)

    def _do_probe(self, url, name):
        def _do():
            source = CustomSource(url, name)
            result = source.probe()

            if result.compatible and source._image_urls:
                test_url = source._image_urls[0]
                self.after(
                    0,
                    lambda: self._progress_label.configure(
                        text="Step 5/5: Testing download of first image..."
                    ),
                )
                try:
                    from core.cache import get_session
                    resp = get_session().head(test_url, timeout=10)
                    ct = resp.headers.get("Content-Type", "")
                    if "image" not in ct and resp.status_code >= 400:
                        result.compatible = False
                        result.error_message = (
                            f"Found image URLs but download test failed "
                            f"(HTTP {resp.status_code}, Content-Type: {ct})"
                        )
                except Exception as e:
                    result.compatible = False
                    result.error_message = (
                        f"Found image URLs but download test failed: {e}"
                    )

            self.after(0, lambda: self._on_scan_complete(source, result))

        threading.Thread(target=_do, daemon=True).start()

    def _on_scan_complete(self, source: CustomSource, result: CompatibilityResult):
        self._probe_running = False
        self._progress_bar.set(1.0)
        self._compatibility = result
        self._custom_source = source

        if result.compatible:
            lines = [
                "SCAN COMPLETE - Source is compatible!",
                f"Type: {result.source_type}",
                f"Images found: {result.image_count}",
            ]
            if result.categories:
                lines.append(f"Categories: {', '.join(result.categories)}")
            if result.supports_search:
                lines.append("Search: Supported")
            self._progress_label.configure(text="All checks passed!")
            self._status_label.configure(text="\n".join(lines), text_color="#00cc66")
            self._add_btn.configure(state="normal")
        else:
            self._progress_label.configure(text="Scan failed")
            self._status_label.configure(
                text=f"NOT COMPATIBLE:\n{result.error_message}",
                text_color="#ff4444",
            )
            self._add_btn.configure(state="disabled")

    def _on_add(self):
        if not self._custom_source or not self._compatibility:
            return

        name = self._name_entry.get().strip() or self._custom_source.name
        url = self._url_entry.get().strip()

        self._custom_source.name = name
        self._custom_source.base_url = url.rstrip("/")
        self.registry.sources[name] = self._custom_source

        custom_sources = self.config.get("custom_sources", [])
        custom_sources.append({"url": url, "name": name})
        self.config.set("custom_sources", custom_sources)

        enabled = self.config.get("enabled_sources", [])
        if name not in enabled:
            enabled.append(name)
            self.config.set("enabled_sources", enabled)

        self._on_change()
        self.destroy()

    def _on_remove_and_retry(self):
        self._url_entry.delete(0, "end")
        self._name_entry.delete(0, "end")
        self._progress_bar.set(0)
        self._progress_label.configure(text="Enter a new URL above and press Enter")
        self._status_label.configure(text="", text_color="gray")
        self._add_btn.configure(state="disabled")
        self._remove_btn.pack_forget()
        self._compatibility = None
        self._custom_source = None
        self._probe_running = False

    def destroy(self):
        for tid in self._after_ids:
            try:
                self.after_cancel(tid)
            except Exception:
                pass
        self._after_ids.clear()
        super().destroy()
