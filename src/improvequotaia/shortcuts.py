"""Raccourcis pour relancer ImproveQuotaIa sans démarrage automatique : menu des applications et bureau.

Linux   : fichier .desktop (menu : ~/.local/share/applications ; bureau : dossier XDG du bureau,
          rendu exécutable et « de confiance » pour GNOME) ;
Windows : raccourcis .lnk (menu Démarrer et Bureau), créés via PowerShell / WScript.Shell ;
macOS   : petite application ~/Applications/ImproveQuotaIa.app (Launchpad, Spotlight) + alias sur le
          bureau. Inutile pour la version .app téléchargée, déjà dans Applications.
"""
from __future__ import annotations

import os
import plistlib
import shlex
import shutil
import stat
import sys
from pathlib import Path
from typing import Optional

from .i18n import t
from .paths import APP_NAME, APP_SLUG
from .platform_utils import _quote, launch_command
from .utils import run_quiet

MENU, DESKTOP = "menu", "desktop"


def desktop_dir() -> Path:
    if sys.platform.startswith("linux") and shutil.which("xdg-user-dir"):
        try:
            out = run_quiet(["xdg-user-dir", "DESKTOP"], timeout=5).stdout.strip()
            if out and Path(out).is_dir():
                return Path(out)
        except Exception:
            pass
    if sys.platform == "win32":
        for base in (os.environ.get("OneDrive"), os.environ.get("USERPROFILE")):
            if base and (Path(base) / "Desktop").is_dir():
                return Path(base) / "Desktop"
    return Path.home() / "Desktop"


def running_from_app_bundle() -> bool:
    return sys.platform == "darwin" and getattr(sys, "frozen", False) and ".app/Contents/MacOS" in sys.executable


def shortcut_path(kind: str) -> Path:
    if sys.platform == "win32":
        programs = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") \
            / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        return (programs if kind == MENU else desktop_dir()) / f"{APP_NAME}.lnk"
    if sys.platform == "darwin":
        return (Path.home() / "Applications" if kind == MENU else desktop_dir()) / f"{APP_NAME}.app"
    apps = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "applications"
    return (apps if kind == MENU else desktop_dir()) / f"{APP_SLUG}.desktop"


def has_shortcut(kind: str) -> bool:
    if kind == MENU and running_from_app_bundle():
        return True
    path = shortcut_path(kind)
    return path.exists() or path.is_symlink()


def desktop_entry(icon: Optional[Path]) -> str:
    cmd = " ".join(_quote(c) for c in launch_command())
    settings = " ".join(_quote(c) for c in launch_command("--settings"))
    return ("[Desktop Entry]\nType=Application\n"
            f"Name={APP_NAME}\nComment={t('shortcut.comment')}\n"
            f"Exec={cmd}\nIcon={icon or 'utilities-system-monitor'}\nTerminal=false\n"
            "Categories=Utility;\nKeywords=AI;quota;Claude;Codex;Gemini;Grok;\n"
            f"StartupWMClass={APP_NAME}\nActions=settings;\n\n"
            f"[Desktop Action settings]\nName={t('tray.settings')}\nExec={settings}\n")


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _windows_shortcut(path: Path, icon: Optional[Path]) -> None:
    cmd = launch_command()
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:QP_LNK); "
              "$s.TargetPath = $env:QP_TARGET; $s.Arguments = $env:QP_ARGS; "
              "$s.WorkingDirectory = $env:USERPROFILE; "
              "if ($env:QP_ICON) { $s.IconLocation = $env:QP_ICON }; $s.Save()")
    env = dict(os.environ, QP_LNK=str(path), QP_TARGET=cmd[0], QP_ARGS=" ".join(_quote(c) for c in cmd[1:]),
               QP_ICON=str(icon) if icon else "")
    result = run_quiet(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=30, env=env)
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or "PowerShell")


def _mac_app(path: Path, icon: Optional[Path]) -> None:
    macos = path / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    exe = macos / APP_NAME
    exe.write_text("#!/bin/sh\nexec " + " ".join(shlex.quote(c) for c in launch_command()) + ' "$@"\n',
                   encoding="utf-8")
    exe.chmod(0o755)
    info = {"CFBundleName": APP_NAME, "CFBundleDisplayName": APP_NAME, "CFBundleExecutable": APP_NAME,
            "CFBundleIdentifier": "io.github.maxft68.improvequotaia.launcher", "CFBundlePackageType": "APPL",
            "LSUIElement": True}
    if icon and icon.suffix == ".icns" and icon.exists():
        resources = path / "Contents" / "Resources"
        resources.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon, resources / "improvequotaia.icns")
        info["CFBundleIconFile"] = "improvequotaia.icns"
    with open(path / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(info, f)


def set_shortcut(kind: str, enabled: bool, icons: Optional[dict] = None) -> None:
    """icons : {"png": Path, "ico": Path, "icns": Path} (selon ce qui a pu être généré)."""
    icons = icons or {}
    path = shortcut_path(kind)
    if not enabled:
        if not (kind == MENU and running_from_app_bundle()):
            _remove(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        _windows_shortcut(path, icons.get("ico"))
    elif sys.platform == "darwin":
        if kind == MENU:
            if not running_from_app_bundle():
                _mac_app(path, icons.get("icns"))
        else:
            target = Path(sys.executable).parents[2] if running_from_app_bundle() else shortcut_path(MENU)
            if not target.exists():
                _mac_app(target, icons.get("icns"))
            _remove(path)
            path.symlink_to(target)
    else:
        path.write_text(desktop_entry(icons.get("png")), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        if kind == DESKTOP and shutil.which("gio"):  # GNOME : autoriser le lancement sans confirmation
            try:
                run_quiet(["gio", "set", str(path), "metadata::trusted", "true"], timeout=5)
            except Exception:
                pass
