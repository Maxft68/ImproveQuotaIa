"""z.ai — GLM Coding Plan : quotas de la fenêtre 5 h (et hebdomadaire selon l'offre) — EXPÉRIMENTAL.

Clé, dans l'ordre : $Z_AI_API_KEY / $ZAI_API_KEY, puis la configuration de Claude Code quand elle
pointe vers z.ai (ANTHROPIC_BASE_URL contenant « z.ai » + ANTHROPIC_AUTH_TOKEN, dans l'environnement
ou dans le bloc "env" de ~/.claude/settings.json) — l'usage le plus courant du GLM Coding Plan.
Source : GET https://api.z.ai/api/monitor/usage/quota/limit (data.limits[] : type, percentage,
nextResetTime en ms). Méthode documentée par CodexBar (MIT) ; non testée avec un vrai compte.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from ..i18n import t
from ..paths import claude_dir
from ..utils import fnum, parse_time
from .base import FIVE_H, WEEK, Bucket, Provider, ProviderError, ProviderResult, ToolMissing, window_id
from .http import HttpError, request_json

GROUP = ("zai", "GLM (z.ai)")
QUOTA_URL = "https://api.z.ai/api/monitor/usage/quota/limit"
UNIT_SECONDS = {"MINUTE": 60, "MINUTES": 60, "HOUR": 3600, "HOURS": 3600, "DAY": 86400, "DAYS": 86400,
                "WEEK": WEEK, "WEEKS": WEEK, "MONTH": 30 * 86400, "MONTHS": 30 * 86400}


def find_key():
    for var in ("Z_AI_API_KEY", "ZAI_API_KEY"):
        if os.environ.get(var):
            return os.environ[var].strip()
    if "z.ai" in os.environ.get("ANTHROPIC_BASE_URL", "") and os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return os.environ["ANTHROPIC_AUTH_TOKEN"].strip()
    try:
        with open(claude_dir() / "settings.json", encoding="utf-8") as f:
            env = (json.load(f) or {}).get("env") or {}
    except (OSError, ValueError, AttributeError):
        return None
    if "z.ai" in str(env.get("ANTHROPIC_BASE_URL", "")) and env.get("ANTHROPIC_AUTH_TOKEN"):
        return str(env["ANTHROPIC_AUTH_TOKEN"]).strip()
    return None


def _duration(limit: dict):
    unit, number = limit.get("unit"), fnum(limit.get("number"))
    if isinstance(unit, str) and number:
        mult = UNIT_SECONDS.get(unit.upper())
        if mult:
            return int(number * mult)
    return None


def parse_limits(data: dict, now: datetime):
    """Réponse du quota → Buckets (fenêtres de jetons uniquement). Fonction pure, testée."""
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    limits = [x for x in payload.get("limits") or [] if isinstance(x, dict)
              and str(x.get("type", "")).upper() in ("TOKENS_LIMIT", "CREDIT_LIMIT")]
    rows = []
    for limit in limits:
        pct = fnum(limit.get("percentage"))
        usage, current = fnum(limit.get("usage")), fnum(limit.get("currentValue"))
        if usage and current is not None:
            pct = current / usage * 100
        if pct is None:
            continue
        rows.append((_duration(limit), parse_time(limit.get("nextResetTime")), min(100.0, max(0.0, pct))))
    if not rows:
        raise ProviderError(t("err.zai_no_data"))
    # Durée inconnue : la fenêtre qui se réinitialise le plus tôt est la 5 h, la suivante l'hebdomadaire.
    rows.sort(key=lambda r: (r[0] is None, r[0] or 0, r[1] or now))
    buckets = []
    for i, (duration, reset_at, pct) in enumerate(rows):
        window_s = duration or (FIVE_H if i == 0 else WEEK)
        buckets.append(Bucket(key=f"zai/{i}", group=GROUP[0], group_label=GROUP[1], win=window_id(window_s / 60),
                              frac=pct / 100.0, reset_at=reset_at, window_s=window_s))
    plan = next((payload.get(k) for k in ("planName", "plan", "plan_type", "packageName", "level")
                 if payload.get(k)), None)
    return buckets, plan


class ZaiProvider(Provider):
    id = "zai"
    label = "GLM Coding Plan (z.ai)"
    title = "GLM · Z.AI"
    groups = [GROUP]
    interval = 60.0
    experimental = True

    def detect(self) -> bool:
        return find_key() is not None

    def fetch(self) -> ProviderResult:
        key = find_key()
        if not key:
            raise ToolMissing(t("err.zai_missing"))
        try:
            data = request_json(QUOTA_URL, {"authorization": f"Bearer {key}"})
        except HttpError as e:
            if e.code in (401, 403):
                raise ProviderError(t("err.zai_key_refused"))
            raise
        buckets, plan = parse_limits(data, datetime.now(timezone.utc))
        return ProviderResult(buckets, time.time(), title_extra=str(plan) if plan else None)
