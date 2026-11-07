"""Grok Build (xAI, abonnement SuperGrok) : pool d'utilisation hebdomadaire — EXPÉRIMENTAL.

Jeton : celui enregistré par `grok login` dans ~/.grok/auth.json (ou $GROK_HOME, ou $GROK_OAUTH_TOKEN).
Le CLI Grok le renouvelle lui-même ; ImproveQuotaIa ne fait que le lire.
Source : GET https://cli-chat-proxy.grok.com/v1/billing?format=credits (part consommée + période).
Méthode documentée par CodexBar (MIT) ; non testée avec un vrai compte au moment de l'écriture.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from ..i18n import t
from ..utils import parse_time
from .base import Bucket, Provider, ProviderError, ProviderResult, ToolMissing, window_id
from .http import HttpError, request_json

GROUP = ("grok", "Grok")
BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
SETTINGS_URL = "https://cli-chat-proxy.grok.com/v1/settings"


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")


def read_token():
    """(jeton, expiration) depuis $GROK_OAUTH_TOKEN ou auth.json (entrée SuperGrok préférée)."""
    env = os.environ.get("GROK_OAUTH_TOKEN")
    if env:
        return env.strip(), None
    try:
        with open(grok_home() / "auth.json", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ToolMissing(t("err.grok_missing"))
    except ValueError:
        raise ProviderError(t("err.grok_missing"))
    if not isinstance(data, dict):
        raise ProviderError(t("err.grok_missing"))
    entries = [(k, v) for k, v in data.items() if isinstance(v, dict) and v.get("key")]
    entries.sort(key=lambda kv: 0 if kv[0].startswith("https://auth.x.ai") else
                 1 if kv[0].startswith("https://accounts.x.ai") else 2)
    if not entries:
        raise ToolMissing(t("err.grok_missing"))
    entry = entries[0][1]
    return entry["key"], parse_time(entry.get("expires_at"))


def _val(obj):
    """Les montants sont au format { "val": <centimes> }."""
    if isinstance(obj, dict):
        obj = obj.get("val")
    try:
        return float(obj)
    except (TypeError, ValueError):
        return None


def parse_billing(data: dict):
    """Réponse de /v1/billing → (Bucket, offre). Fonction pure, testée."""
    cfg = data.get("config") if isinstance(data.get("config"), dict) else data
    pct = cfg.get("creditUsagePercent")
    if pct is None:
        used, cap = _val(cfg.get("onDemandUsed")), _val(cfg.get("onDemandCap"))
        if used is not None and cap:
            pct = used / cap * 100
    if pct is None:  # ancien format
        usage = cfg.get("usage") or {}
        used, limit = _val(usage.get("totalUsed")), _val(cfg.get("monthlyLimit"))
        if used is not None and limit:
            pct = used / limit * 100
    period = cfg.get("currentPeriod") or cfg.get("billingCycle") or {}
    end = parse_time(period.get("end") or period.get("billingPeriodEnd") or cfg.get("billingPeriodEnd"))
    start = parse_time(period.get("start") or period.get("billingPeriodStart") or cfg.get("billingPeriodStart"))
    if pct is None:
        raise ProviderError(t("err.grok_no_data"))
    window_s = int((end - start).total_seconds()) if end and start and end > start else None
    products = [p for p in cfg.get("productUsage") or [] if isinstance(p, dict)]
    tooltip = "\n".join(f"{p.get('product')} : {float(p.get('usagePercent') or 0):.0f} %" for p in products) or None
    bucket = Bucket(key="grok/credits", group=GROUP[0], group_label=GROUP[1],
                    win=window_id(window_s / 60) if window_s else "7d", frac=float(pct) / 100.0,
                    reset_at=end, window_s=window_s, tooltip=tooltip)
    return bucket, data.get("subscriptionTier") or cfg.get("subscriptionTier")


class GrokProvider(Provider):
    id = "grok"
    label = "Grok"
    title = "GROK"
    groups = [GROUP]
    interval = 60.0
    experimental = True

    def __init__(self):
        self.plan = None

    def detect(self) -> bool:
        return (grok_home() / "auth.json").exists() or shutil.which("grok") is not None \
            or bool(os.environ.get("GROK_OAUTH_TOKEN"))

    def fetch(self) -> ProviderResult:
        token, expires = read_token()
        if expires and expires < datetime.now(timezone.utc):
            raise ProviderError(t("err.grok_token_expired"))
        headers = {"Authorization": f"Bearer {token}", "x-xai-token-auth": "xai-grok-cli"}
        try:
            data = request_json(BILLING_URL, headers)
        except HttpError as e:
            if e.code in (401, 403):
                raise ProviderError(t("err.grok_token_expired"))
            raise
        bucket, tier = parse_billing(data)
        if self.plan is None:
            try:
                self.plan = request_json(SETTINGS_URL, headers, timeout=5).get("subscription_tier_display")
            except ProviderError:
                self.plan = ""
        return ProviderResult([bucket], time.time(), title_extra=self.plan or tier or None)
