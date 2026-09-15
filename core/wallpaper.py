import ctypes
from ctypes import wintypes
import winreg

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

STYLES = {
    "Fill": 10,
    "Fit": 6,
    "Stretch": 2,
    "Tile": 0,
    "Center": 0,
    "Span": 22,
}

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def set_wallpaper(path: str, style: str = "Fill") -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            0,
            winreg.KEY_SET_VALUE,
        )
        wallpaper_style = STYLES.get(style, 10)
        if style == "Fill":
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        elif style == "Fit":
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "6")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        elif style == "Stretch":
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "2")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        elif style == "Tile":
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "0")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "1")
        elif style == "Center":
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "0")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        elif style == "Span":
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "22")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(key)

        result = user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )
        return bool(result)
    except Exception:
        return False


def get_current_wallpaper() -> str:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, "Wallpaper")
        winreg.CloseKey(key)
        return value
    except Exception:
        return ""


def get_screen_resolution() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
