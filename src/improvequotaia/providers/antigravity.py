"""Antigravity CLI (Google) : quotas Gemini, Argon, Claude / GPT.

Source : `agy -p /usage --output-format json`. Cette commande ne consomme aucun quota.
`--log-file <null>` évite qu'agy écrive un fichier de log (~28 Ko) à chaque appel.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import psutil

from ..i18n import t
from ..utils import parse_time, run_quiet
from .base import FIVE_H, WEEK, Bucket, Provider, ProviderError, ProviderResult, ToolMissing

KNOWN = [("ag-gemini", "Gemini"), ("ag-argon", "Argon"), ("ag-3p", "Claude / GPT")]
# Chaque relevé coûte ~0,6 s de processeur : espacé pour préserver le CPU et la mémoire.
ACTIVE_INTERVAL, IDLE_INTERVAL = 30.0, 180.0
AGY_NAMES = {"agy", "agy.exe", "antigravity", "antigravity.exe"}


def agy_in_use() -> bool:
    """Vrai si Antigravity tourne (hors les relevés lancés par ImproveQuotaIa lui-même)."""
    me = os.getpid()
    for proc in psutil.process_iter(["name", "ppid"]):
        if (proc.info.get("name") or "").lower() in AGY_NAMES and proc.info.get("ppid") != me:
            return True
    return False
WINDOWS = {"5h": ("5h", FIVE_H), "weekly": ("7d", WEEK)}


def agy_path():
    found = shutil.which("agy")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "agy"
    return str(fallback) if fallback.exists() else None


def group_for(name: str):
    """Identifiant stable d'après le nom renvoyé par le serveur (qui peut changer de version)."""
    low = (name or "").lower()
    if "argon" in low:
        return KNOWN[1]
    if "claude" in low or "gpt" in low:
        return KNOWN[2]
    if "gemini" in low:
        return KNOWN[0]
    return "ag-" + re.sub(r"[^a-z0-9]+", "-", low).strip("-"), name or "?"


def parse_usage(payload: dict):
    """Transforme la réponse JSON d'agy en Buckets (fonction pure, testée)."""
    if payload.get("status") != "SUCCESS":
        raise ProviderError(str(payload.get("response") or payload.get("status"))[:160])
    try:
        groups = payload["command"]["data"]["groups"]
    except (KeyError, TypeError):
        raise ProviderError(t("err.agy_unreadable"))
    buckets = []
    for g in groups:
        gid, glabel = group_for(g.get("name"))
        raw = sorted(g.get("buckets", []), key=lambda b: 0 if b.get("window") == "5h" else 1)
        if raw and not any(b.get("window") == "5h" for b in raw):
            # Ex. Argon sur un plan Pro : seule une limite hebdomadaire existe côté serveur.
            buckets.append(Bucket(key=f"{gid}/5h-absent", group=gid, group_label=glabel, win="5h",
                                  frac=None, reset_at=None, window_s=FIVE_H, disabled=True,
                                  note=t("note.no_5h"), tooltip=t("tip.no_5h")))
        for b in raw:
            win, secs = WINDOWS.get(b.get("window"), (b.get("window") or "?", None))
            disabled = bool(b.get("disabled"))
            remaining = b.get("remaining_fraction")
            buckets.append(Bucket(
                key=b.get("id") or f"{gid}/{b.get('name')}", group=gid, group_label=glabel, win=win,
                frac=None if remaining is None else 1.0 - remaining,
                reset_at=None if disabled else parse_time(b.get("reset_time")),
                window_s=secs, disabled=disabled, note=t("note.disabled") if disabled else None,
                tooltip="\n".join(x for x in (g.get("description"), b.get("description")) if x) or None,
            ))
    return buckets


class AntigravityProvider(Provider):
    id = "antigravity"
    label = "Antigravity"
    title = "ANTIGRAVITY"
    groups = KNOWN

    @property
    def interval(self) -> float:
        return ACTIVE_INTERVAL if agy_in_use() else IDLE_INTERVAL

    def detect(self) -> bool:
        return agy_path() is not None

    def fetch(self) -> ProviderResult:
        agy = agy_path()
        if not agy:
            raise ToolMissing(t("err.agy_missing"))
        try:
            proc = run_quiet([agy, "--log-file", os.devnull, "-p", "/usage", "--output-format", "json"],
                             timeout=45, cwd=str(Path.home()))
        except OSError as e:
            raise ToolMissing(str(e))
        except subprocess.TimeoutExpired as e:
            raise ProviderError(t("err.agy_timeout")) from e
        if proc.returncode != 0:
            lines = (proc.stderr or proc.stdout).strip().splitlines()
            raise ProviderError(lines[-1][:160] if lines else f"agy code {proc.returncode}")
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            raise ProviderError(t("err.agy_unreadable"))
        return ProviderResult(parse_usage(payload), time.time())
