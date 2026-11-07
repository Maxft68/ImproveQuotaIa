"""Emplacements des fichiers selon le système (aucune dépendance à Qt : utilisé par la status line)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ImproveQuotaIa"
APP_SLUG = "improvequotaia"


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / APP_SLUG


def cache_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME / "Cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / APP_NAME
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / APP_SLUG


def data_dir() -> Path:
    """Fichiers durables de l'application (icônes des raccourcis…)."""
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_SLUG


def claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def codex_dir() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def claude_statusline_cache() -> Path:
    return cache_dir() / "claude_statusline.json"
