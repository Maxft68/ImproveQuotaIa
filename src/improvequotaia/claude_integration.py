"""Branchement de la status line de Claude Code (~/.claude/settings.json), avec l'accord de
l'utilisateur. Une sauvegarde du fichier est faite avant toute modification, et une status line
existante est conservée (rappelée par la nôtre)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .config import load_config, save_config
from .paths import claude_dir
from .platform_utils import launch_command

LEGACY_MARKERS = ("moniteur-ia/statusline.py", "-m quotapace")  # anciens noms, remplacés sans chaînage


def settings_path():
    return claude_dir() / "settings.json"


def our_command() -> str:
    if getattr(sys, "frozen", False):
        # Exécutable autonome : petit exécutable console livré à côté (stdout fiable sous Windows)
        name = "improvequotaia-statusline" + (".exe" if sys.platform == "win32" else "")
        helper = Path(sys.executable).with_name(name)
        cmd = [str(helper)] if helper.exists() else launch_command("--statusline")
    else:
        cmd = launch_command("--statusline")
        if sys.platform == "win32":
            cmd = [c.replace("pythonw.exe", "python.exe") for c in cmd]  # la status line écrit sur stdout
    return " ".join(f'"{c}"' if " " in c else c for c in cmd)


def _read_settings():
    path = settings_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)  # ValueError si le fichier est invalide : on ne touche à rien
    if not isinstance(data, dict):
        raise ValueError("settings.json n'est pas un objet JSON")
    return data


def status() -> str:
    """'ours', 'other', 'none' ou 'error'."""
    try:
        current = (_read_settings().get("statusLine") or {}).get("command", "")
    except (OSError, ValueError, AttributeError):
        return "error"
    if not current:
        return "none"
    if "improvequotaia" in current and "statusline" in current:
        return "ours"
    return "other"


def install() -> None:
    data = _read_settings()
    path = settings_path()
    if path.exists():
        shutil.copy2(path, path.with_name("settings.json.improvequotaia-backup"))
    previous = (data.get("statusLine") or {}).get("command", "")
    cfg = load_config()
    if previous and "improvequotaia" not in previous and not any(m in previous for m in LEGACY_MARKERS):
        cfg["statusline_chain"] = previous
        save_config(cfg)
    data["statusLine"] = {"type": "command", "command": our_command()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def uninstall() -> None:
    data = _read_settings()
    cfg = load_config()
    chain = cfg.get("statusline_chain")
    if chain:
        data["statusLine"] = {"type": "command", "command": chain}
        cfg["statusline_chain"] = None
        save_config(cfg)
    else:
        data.pop("statusLine", None)
    with open(settings_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
