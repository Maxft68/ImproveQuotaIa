"""Codex CLI (OpenAI, abonnement ChatGPT) : quotas 5 h et hebdomadaire — EXPÉRIMENTAL.

Codex écrit dans ses fichiers de session (~/.codex/sessions/AAAA/MM/JJ/rollout-*.jsonl) des
évènements `token_count` contenant `rate_limits.primary` (≈ 5 h) et `rate_limits.secondary`
(≈ 7 j) avec `used_percent`, `window_minutes` et `resets_in_seconds` (ou `resets_at`).
Format observé par la communauté, non documenté officiellement : à comparer avec `/status`.
Les valeurs sont celles du dernier message envoyé à Codex.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone

from ..i18n import t
from ..paths import codex_dir
from ..utils import parse_time
from .base import Bucket, Provider, ProviderError, ProviderResult, ToolMissing, window_id

GROUP = ("codex", "Codex")
TAIL_BYTES = 512 * 1024


def recent_rollouts(days: int = 8, limit: int = 12):
    sessions = codex_dir() / "sessions"
    if not sessions.is_dir():
        return []
    today = datetime.now().date()
    files = []
    for delta in range(days):
        day = today - timedelta(days=delta)
        folder = sessions / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}"
        if folder.is_dir():
            files.extend(folder.glob("rollout-*.jsonl"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def last_rate_limits(path):
    """Dernier évènement contenant rate_limits dans la fin du fichier : (horodatage, rate_limits)."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            chunk = f.read()
    except OSError:
        return None
    for line in reversed(chunk.splitlines()):
        if b'"rate_limits"' not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        payload = obj.get("payload") or {}
        limits = payload.get("rate_limits") or (payload.get("info") or {}).get("rate_limits")
        if isinstance(limits, dict) and limits:
            return parse_time(obj.get("timestamp")) or datetime.now(timezone.utc), limits
    return None


def buckets_from_limits(stamp: datetime, limits: dict):
    buckets = []
    for name in ("primary", "secondary"):
        w = limits.get(name)
        if not isinstance(w, dict) or w.get("used_percent") is None:
            continue
        minutes = w.get("window_minutes")
        if w.get("resets_at") is not None:
            reset_at = parse_time(w["resets_at"])
        elif w.get("resets_in_seconds") is not None:
            reset_at = stamp + timedelta(seconds=float(w["resets_in_seconds"]))
        else:
            reset_at = None
        buckets.append(Bucket(key=f"codex/{name}", group=GROUP[0], group_label=GROUP[1],
                              win=window_id(minutes), frac=float(w["used_percent"]) / 100.0,
                              reset_at=reset_at, window_s=int(minutes * 60) if minutes else None))
    return buckets


class CodexProvider(Provider):
    id = "codex"
    label = "Codex"
    title = "CODEX"
    groups = [GROUP]
    experimental = True

    def detect(self) -> bool:
        return codex_dir().is_dir() or shutil.which("codex") is not None

    def fetch(self) -> ProviderResult:
        if not self.detect():
            raise ToolMissing(t("err.codex_missing"))
        best = None
        for path in recent_rollouts():
            found = last_rate_limits(path)
            if found and (best is None or found[0] > best[0]):
                best = found
        if best is None:
            raise ProviderError(t("err.codex_no_data"))
        buckets = buckets_from_limits(*best)
        if not buckets:
            raise ProviderError(t("err.codex_no_data"))
        return ProviderResult(buckets, best[0].timestamp(), "Codex")
