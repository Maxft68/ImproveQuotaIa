"""Configuration persistante (JSON) — sans dépendance à Qt."""
from __future__ import annotations

import copy
import json
import os
import tempfile

from .paths import config_dir

DISPLAYS = ("hud", "tray", "main")

DEFAULTS = {
    "first_run_done": False,
    "language": "auto",          # auto | fr | en
    "providers": {},             # id -> bool (absent = activé si détecté)
    "hud": True,
    "corner": "top-right",       # top-right | bottom-right | bottom-left | top-left
    "opacity": 0.9,
    # Éléments masqués par affichage. On stocke ce qui est caché (et non ce qui est montré)
    # pour qu'un nouveau groupe de quota apparaisse automatiquement.
    "hidden": {"hud": [], "tray": [], "main": []},
    "statusline_chain": None,    # ancienne status line de Claude Code, rappelée par la nôtre
    "tray_text": True,           # Linux : texte dans la barre du haut (indicateur AppIndicator)
}


def config_path():
    return config_dir() / "config.json"


def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(config_path(), encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(saved, dict):
        return cfg
    hidden = saved.pop("hidden", None)
    providers = saved.pop("providers", None)
    cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
    if isinstance(hidden, dict):
        for display in DISPLAYS:
            if isinstance(hidden.get(display), list):
                cfg["hidden"][display] = hidden[display]
    if isinstance(providers, dict):
        cfg["providers"] = {k: bool(v) for k, v in providers.items()}
    return cfg


def save_config(cfg: dict) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, config_path())


def is_shown(cfg: dict, display: str, item: str, win: str | None = None) -> bool:
    hidden = cfg["hidden"].get(display, [])
    return item not in hidden and (win is None or win not in hidden)
