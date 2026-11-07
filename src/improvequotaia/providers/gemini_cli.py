"""Gemini CLI avec un compte Google (Code Assist) : quotas journaliers par famille de modèles — EXPÉRIMENTAL.

Depuis le 18/06/2026, Google ne fournit plus ce quota aux comptes individuels, AI Pro et Ultra
(ils sont renvoyés vers Antigravity) : ce module sert surtout aux comptes Code Assist entreprise.
Identifiants : ~/.gemini/oauth_creds.json (connexion « Login with Google »). Le jeton est renouvelé
par Gemini CLI lui-même ; une session avec clé API n'a pas de quota à lire.
Source : cloudcode-pa.googleapis.com v1internal:loadCodeAssist puis v1internal:retrieveUserQuota
(format vérifié dans le code de Gemini CLI : buckets[] avec modelId, remainingFraction, resetTime).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ..i18n import t
from ..utils import parse_time
from .base import Bucket, Provider, ProviderError, ProviderResult, ToolMissing
from .http import HttpError, request_json

GROUP = ("gemini-cli", "Gemini CLI")
BASE = "https://cloudcode-pa.googleapis.com/v1internal"
DAY = 86400
TIERS = (("lite", "Flash Lite"), ("flash", "Flash"), ("pro", "Pro"))  # « lite » testé avant « flash »


def creds_path() -> Path:
    return Path.home() / ".gemini" / "oauth_creds.json"


def tier_of(model_id: str):
    low = (model_id or "").lower()
    for needle, label in TIERS:
        if needle in low:
            return label
    return model_id or "?"


def parse_quota(data: dict):
    """Réponse de retrieveUserQuota → une ligne par famille (la plus entamée). Fonction pure, testée."""
    worst = {}
    for b in data.get("buckets") or []:
        if not isinstance(b, dict) or not b.get("modelId") or b.get("remainingFraction") is None:
            continue
        tier = tier_of(b["modelId"])
        if tier not in worst or b["remainingFraction"] < worst[tier]["remainingFraction"]:
            worst[tier] = b
    order = {"Pro": 0, "Flash": 1, "Flash Lite": 2}
    buckets = []
    for tier, b in sorted(worst.items(), key=lambda kv: order.get(kv[0], 9)):
        buckets.append(Bucket(key=f"gemini-cli/{tier}", group=GROUP[0], group_label=GROUP[1], win="1d",
                              win_label=tier, frac=max(0.0, 1.0 - float(b["remainingFraction"])),
                              reset_at=parse_time(b.get("resetTime")), window_s=DAY, tooltip=b["modelId"]))
    if not buckets:
        raise ProviderError(t("err.gemini_cli_no_data"))
    return buckets


class GeminiCliProvider(Provider):
    id = "gemini-cli"
    label = "Gemini CLI"
    title = "GEMINI CLI"
    groups = [GROUP]
    interval = 60.0
    experimental = True

    def __init__(self):
        self.project = None

    def detect(self) -> bool:
        return creds_path().exists()

    def fetch(self) -> ProviderResult:
        try:
            with open(creds_path(), encoding="utf-8") as f:
                creds = json.load(f)
        except FileNotFoundError:
            raise ToolMissing(t("err.gemini_cli_missing"))
        except ValueError:
            raise ProviderError(t("err.gemini_cli_missing"))
        token = creds.get("access_token")
        expiry = parse_time(creds.get("expiry_date"))
        if not token:
            raise ToolMissing(t("err.gemini_cli_missing"))
        if expiry and expiry < datetime.now(timezone.utc):
            raise ProviderError(t("err.gemini_cli_expired"))
        headers = {"Authorization": f"Bearer {token}"}
        try:
            if self.project is None:
                info = request_json(f"{BASE}:loadCodeAssist", headers,
                                    {"metadata": {"ideType": "GEMINI_CLI", "pluginType": "GEMINI"}})
                project = info.get("cloudaicompanionProject")
                self.project = project.get("id") if isinstance(project, dict) else project or ""
            data = request_json(f"{BASE}:retrieveUserQuota", headers,
                                {"project": self.project} if self.project else {})
        except HttpError as e:
            if e.code == 403 and "SUBSCRIPTION_REQUIRED" in e.body:
                raise ProviderError(t("err.gemini_consumer"))
            if e.code == 401:
                raise ProviderError(t("err.gemini_cli_expired"))
            raise
        return ProviderResult(parse_quota(data), time.time())
