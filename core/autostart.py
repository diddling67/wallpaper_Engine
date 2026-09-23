import sys
import winreg
from pathlib import Path

APP_NAME = "WallpaperEngine"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_exe_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return f'"{sys.executable}" "{Path(__file__).parent.parent / "wallpaper_engine.py"}"'


def is_autostart_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(enable: bool):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_exe_path())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass
