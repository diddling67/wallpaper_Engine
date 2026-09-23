import threading
import pystray
from PIL import Image, ImageDraw


def create_icon_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=10, fill=(30, 100, 200))
    draw.text((14, 14), "WE", fill="white")
    return img


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self._icon = None
        self._thread = None

    def start(self):
        menu = pystray.Menu(
            pystray.MenuItem("Open", self._on_show, default=True),
            pystray.MenuItem("Play/Pause", self._on_toggle_play),
            pystray.MenuItem("Next Wallpaper", self._on_next),
            pystray.MenuItem("Previous Wallpaper", self._on_prev),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Like Current", self._on_like),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )
        self._icon = pystray.Icon(
            "WallpaperEngine",
            create_icon_image(),
            "Wallpaper Engine",
            menu,
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._icon:
            self._icon.stop()

    def _on_show(self, icon, item):
        try:
            self.app.after(0, self._show_window)
        except Exception:
            pass

    def _show_window(self):
        try:
            self.app.deiconify()
            self.app.lift()
            self.app.focus_force()
        except Exception:
            pass

    def _on_toggle_play(self, icon, item):
        try:
            self.app.after(0, self.app._on_toggle_play)
        except Exception:
            pass

    def _on_next(self, icon, item):
        try:
            self.app.after(0, self.app._on_next)
        except Exception:
            pass

    def _on_prev(self, icon, item):
        try:
            self.app.after(0, self.app._on_prev)
        except Exception:
            pass

    def _on_like(self, icon, item):
        try:
            self.app.after(0, self.app._on_toggle_like)
        except Exception:
            pass

    def _on_quit(self, icon, item):
        try:
            self.app.after(0, self.app._force_quit)
        except Exception:
            pass
