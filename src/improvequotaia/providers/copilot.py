"""GitHub Copilot : requêtes premium (et chat sur l'offre gratuite) du mois — EXPÉRIMENTAL.

Jeton GitHub, dans l'ordre : fichiers de github-copilot (apps.json / hosts.json, utilisés par
copilot.vim, JetBrains…), $COPILOT_GITHUB_TOKEN, `gh auth token`, puis $GH_TOKEN / $GITHUB_TOKEN.
Source : GET https://api.github.com/copilot_internal/user (interface interne, non documentée).
"""
from __future__ import annotations

import calendar
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from ..i18n import t
from ..utils import parse_time, run_quiet
from .base import Bucket, Provider, ProviderError, ProviderResult, ToolMissing
from .http import HttpError, request_json

GROUP = ("copilot", "GitHub Copilot")
USER_URL = "https://api.github.com/copilot_internal/user"
HEADERS = {
    "Editor-Version": "vscode/1.96.2",
    "Editor-Plugin-Version": "copilot-chat/0.26.7",
    "X-Github-Api-Version": "2025-04-01",
}


def _copilot_config_dirs():
    if sys.platform == "win32":
        yield Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "github-copilot"
    yield Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "github-copilot"


def find_token():
    for folder in _copilot_config_dirs():
        for name in ("apps.json", "hosts.json"):
            try:
                with open(folder / name, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            for key, entry in (data.items() if isinstance(data, dict) else []):
                if "github.com" in key and isinstance(entry, dict) and entry.get("oauth_token"):
                    return entry["oauth_token"]
    if os.environ.get("COPILOT_GITHUB_TOKEN"):
        return os.environ["COPILOT_GITHUB_TOKEN"]
    if shutil.which("gh"):
        try:
            out = run_quiet(["gh", "auth", "token"], timeout=10)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:
            pass
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def month_window(reset_at):
    """Durée de la période mensuelle qui se termine à reset_at (même jour du mois précédent)."""
    if reset_at is None:
        return None
    year, month = (reset_at.year, reset_at.month - 1) if reset_at.month > 1 else (reset_at.year - 1, 12)
    day = min(reset_at.day, calendar.monthrange(year, month)[1])
    return int((reset_at - reset_at.replace(year=year, month=month, day=day)).total_seconds())


def _get(d: dict, snake: str):
    camel = snake.split("_")[0] + "".join(w.title() for w in snake.split("_")[1:])
    return d.get(snake, d.get(camel))


def parse_user(data: dict):
    """Réponse de copilot_internal/user → (Buckets, offre). Fonction pure, testée."""
    if data.get("access_type_sku") == "subscription_ended":
        raise ProviderError(t("err.copilot_ended"))
    snaps = _get(data, "quota_snapshots") or {}
    reset_at = parse_time(_get(data, "quota_reset_date"))
    window_s = month_window(reset_at)
    buckets = []
    for name, label in (("premium_interactions", "Premium"), ("chat", "Chat"), ("completions", "Completions")):
        s = _get(snaps, name)
        if not isinstance(s, dict) or s.get("unlimited"):
            continue
        remaining_pct = _get(s, "percent_remaining")
        if remaining_pct is None:
            entitlement, remaining = s.get("entitlement"), s.get("remaining")
            if entitlement and remaining is not None:
                remaining_pct = remaining / entitlement * 100
        if remaining_pct is None:
            continue
        buckets.append(Bucket(key=f"copilot/{name}", group=GROUP[0], group_label=GROUP[1], win="1mo",
                              win_label=label, frac=max(0.0, 1.0 - float(remaining_pct) / 100.0),
                              reset_at=reset_at, window_s=window_s,
                              tooltip=(f"{s.get('remaining')} / {s.get('entitlement')}"
                                       if s.get("entitlement") else None)))
    if not buckets:
        raise ProviderError(t("err.copilot_no_quota"))
    return buckets, _get(data, "copilot_plan")


class CopilotProvider(Provider):
    id = "copilot"
    label = "GitHub Copilot"
    title = "COPILOT"
    groups = [GROUP]
    interval = 120.0
    experimental = True

    def detect(self) -> bool:
        return (Path.home() / ".copilot").is_dir() or shutil.which("copilot") is not None \
            or any((d / "apps.json").exists() or (d / "hosts.json").exists() for d in _copilot_config_dirs())

    def fetch(self) -> ProviderResult:
        token = find_token()
        if not token:
            raise ToolMissing(t("err.copilot_missing"))
        try:
            data = request_json(USER_URL, {"Authorization": f"token {token}", **HEADERS})
        except HttpError as e:
            if e.code in (401, 403, 404):
                raise ToolMissing(t("err.copilot_missing"))
            raise
        buckets, plan = parse_user(data)
        return ProviderResult(buckets, time.time(), title_extra=(plan or "").capitalize() or None)
