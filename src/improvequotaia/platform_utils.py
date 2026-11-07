"""Ce qui dépend du système : commande de lancement, démarrage automatique, plein écran, X11."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import List

from .paths import APP_NAME, APP_SLUG
from .utils import run_quiet

LAUNCH_AGENT_ID = "io.github.maxft68.improvequotaia"


def launch_command(*extra: str) -> List[str]:
    """Commande qui relance l'application (binaire autonome ou module Python)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *extra]
    exe = sys.executable
    if sys.platform == "win32":  # pythonw : pas de fenêtre console au démarrage
        pythonw = Path(exe).with_name("pythonw.exe")
        if pythonw.exists():
            exe = str(pythonw)
    return [exe, "-m", "improvequotaia", *extra]


def _quote(arg: str) -> str:
    return f'"{arg}"' if any(c in arg for c in ' "\t') else arg


# ---------------------------------------------------------------- démarrage automatique

def _linux_autostart_file() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "autostart" / f"{APP_SLUG}.desktop"


def _mac_agent_file() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_ID}.plist"


def autostart_enabled() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                winreg.QueryValueEx(k, APP_NAME)
                return True
        except OSError:
            return False
    if sys.platform == "darwin":
        return _mac_agent_file().exists()
    return _linux_autostart_file().exists()


def set_autostart(enabled: bool) -> None:
    cmd = launch_command("--background")
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, " ".join(_quote(c) for c in cmd))
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except OSError:
                    pass
        return
    if sys.platform == "darwin":
        import plistlib
        path = _mac_agent_file()
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                plistlib.dump({"Label": LAUNCH_AGENT_ID, "ProgramArguments": cmd, "RunAtLoad": True,
                               "ProcessType": "Interactive"}, f)
        elif path.exists():
            path.unlink()
        return
    path = _linux_autostart_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\nType=Application\n"
            f"Name={APP_NAME}\nComment=AI quota pace + CPU/GPU/RAM\n"
            f"Exec={' '.join(_quote(c) for c in cmd)}\n"
            "Icon=utilities-system-monitor\nTerminal=false\n"
            "X-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=5\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


# ---------------------------------------------------------------- plein écran

def fullscreen_active() -> bool:
    """Vrai si l'application au premier plan est en plein écran (jeu, vidéo, présentation).
    macOS : inutile, une app plein écran a son propre « Space » où le HUD n'apparaît pas."""
    if sys.platform == "win32":
        import ctypes
        state = ctypes.c_int(0)
        try:
            if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
                return state.value in (2, 3, 4)  # BUSY, RUNNING_D3D_FULL_SCREEN, PRESENTATION_MODE
        except (AttributeError, OSError):
            pass
        return False
    if sys.platform.startswith("linux") and os.environ.get("DISPLAY") and shutil.which("xprop"):
        try:
            active = run_quiet(["xprop", "-root", "_NET_ACTIVE_WINDOW"], timeout=1).stdout.split()
            wid = active[-1] if active else "0x0"
            if not wid.startswith("0x") or int(wid, 16) == 0:
                return False
            state = run_quiet(["xprop", "-id", wid, "_NET_WM_STATE"], timeout=1).stdout
            return "_NET_WM_STATE_FULLSCREEN" in state
        except Exception:
            return False
    return False


def x11_make_sticky(win_id: int) -> None:
    """Demande au gestionnaire de fenêtres X11 d'afficher la fenêtre sur tous les bureaux.
    À faire avant chaque affichage (la propriété est retirée quand la fenêtre est cachée)."""
    if sys.platform.startswith("linux") and os.environ.get("DISPLAY") and shutil.which("xprop"):
        try:
            run_quiet(["xprop", "-id", str(win_id), "-f", "_NET_WM_DESKTOP", "32c",
                       "-set", "_NET_WM_DESKTOP", "4294967295"], timeout=2)
        except Exception:
            pass
