import ctypes
import winreg

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

STYLES = {
    "Fill": 10,
    "Fit": 6,
    "Stretch": 2,
    "Tile": 1,
    "Center": 0,
    "Span": 22,
}

user32 = ctypes.windll.user32


def set_wallpaper(path: str, style: str = "Fill") -> tuple[bool, str]:
    try:
        style_val = str(STYLES.get(style, 10))
        tile = "1" if style == "Tile" else "0"

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style_val)
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile)
        finally:
            winreg.CloseKey(key)

        result = user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )
        if result:
            return True, ""
        return False, "SystemParametersInfoW returned 0"
    except Exception as e:
        return False, str(e)


def get_current_wallpaper() -> str:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            0,
            winreg.KEY_READ,
        )
        try:
            value, _ = winreg.QueryValueEx(key, "Wallpaper")
            return value
        finally:
            winreg.CloseKey(key)
    except Exception:
        return ""


def get_screen_resolution() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
