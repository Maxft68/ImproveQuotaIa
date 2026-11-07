"""Modules expérimentaux : réponses au format documenté (CodexBar, code source de Gemini CLI)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from improvequotaia.providers import copilot, gemini_cli, grok, zai
from improvequotaia.providers.base import ProviderError, ToolMissing

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- Grok
def test_grok_credits_payload():
    bucket, tier = grok.parse_billing({
        "subscriptionTier": "SuperGrok",
        "config": {"creditUsagePercent": 42.5,
                   "currentPeriod": {"start": "2026-11-03T00:00:00Z", "end": "2026-11-10T00:00:00Z"},
                   "productUsage": [{"product": "GrokBuild", "usagePercent": 40.0},
                                    {"product": "GrokChat", "usagePercent": 2.5}]}})
    assert (bucket.win, bucket.frac, bucket.window_s) == ("7d", pytest.approx(0.425), 7 * 86400)
    assert bucket.reset_at == datetime(2026, 11, 10, tzinfo=timezone.utc)
    assert "GrokBuild : 40 %" in bucket.tooltip and tier == "SuperGrok"


def test_grok_legacy_payload_and_missing_percent():
    bucket, _ = grok.parse_billing({
        "billingCycle": {"billingPeriodStart": "2026-11-01T00:00:00Z", "billingPeriodEnd": "2026-12-01T00:00:00Z"},
        "monthlyLimit": {"val": 1000}, "usage": {"totalUsed": {"val": 250}}})
    assert (bucket.win, bucket.frac) == ("1mo", pytest.approx(0.25))
    with pytest.raises(ProviderError):
        grok.parse_billing({"config": {"currentPeriod": {}}})


def test_grok_token_prefers_supergrok_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("GROK_HOME", str(tmp_path))
    monkeypatch.delenv("GROK_OAUTH_TOKEN", raising=False)
    (tmp_path / "auth.json").write_text(json.dumps({
        "https://accounts.x.ai/sign-in": {"key": "legacy", "expires_at": "2030-01-01T00:00:00Z"},
        "https://auth.x.ai::client": {"key": "supergrok", "expires_at": "2030-01-01T00:00:00Z"}}))
    token, expires = grok.read_token()
    assert token == "supergrok" and expires.year == 2030


def test_grok_without_login(tmp_path, monkeypatch):
    monkeypatch.setenv("GROK_HOME", str(tmp_path))
    monkeypatch.delenv("GROK_OAUTH_TOKEN", raising=False)
    with pytest.raises(ToolMissing):
        grok.read_token()


# ---------------------------------------------------------------- GitHub Copilot
def test_copilot_premium_requests():
    buckets, plan = copilot.parse_user({
        "copilot_plan": "individual", "quota_reset_date": "2026-12-01",
        "quota_snapshots": {"premium_interactions": {"entitlement": 300, "remaining": 120, "percent_remaining": 40.0,
                                                     "unlimited": False},
                            "chat": {"unlimited": True}, "completions": {"unlimited": True}}})
    assert len(buckets) == 1 and plan == "individual"
    b = buckets[0]
    assert (b.win, b.win_label, b.frac) == ("1mo", "Premium", pytest.approx(0.60))
    assert b.window_s == 30 * 86400  # 1er novembre → 1er décembre


def test_copilot_camel_case_and_counts():
    buckets, _ = copilot.parse_user({"quotaResetDate": "2026-12-01T00:00:00Z", "quotaSnapshots": {
        "premiumInteractions": {"entitlement": 50, "remaining": 40}, "chat": {"entitlement": 50, "remaining": 5}}})
    assert [round(b.frac, 2) for b in buckets] == [0.2, 0.9]


def test_copilot_errors():
    with pytest.raises(ProviderError):
        copilot.parse_user({"access_type_sku": "subscription_ended"})
    with pytest.raises(ProviderError):
        copilot.parse_user({"quota_snapshots": {"premium_interactions": {"unlimited": True}}})


def test_month_window_handles_short_months():
    assert copilot.month_window(datetime(2026, 3, 1, tzinfo=timezone.utc)) == 28 * 86400


# ---------------------------------------------------------------- Gemini CLI
def test_gemini_cli_quota_by_family():
    buckets = gemini_cli.parse_quota({"buckets": [
        {"modelId": "gemini-3.8-pro", "remainingFraction": 0.8, "resetTime": "2026-11-08T00:00:00Z"},
        {"modelId": "gemini-3.8-pro-preview", "remainingFraction": 0.6, "resetTime": "2026-11-08T00:00:00Z"},
        {"modelId": "gemini-3.8-flash", "remainingFraction": 0.9},
        {"modelId": "gemini-3.8-flash-lite", "remainingFraction": 1.0},
        {"modelId": "ignored-without-fraction"}]})
    assert [(b.win_label, round(b.frac, 2)) for b in buckets] == [("Pro", 0.4), ("Flash", 0.1), ("Flash Lite", 0.0)]
    assert buckets[0].win == "1d" and buckets[0].tooltip == "gemini-3.8-pro-preview"


def test_gemini_cli_empty():
    with pytest.raises(ProviderError):
        gemini_cli.parse_quota({"buckets": []})


# ---------------------------------------------------------------- z.ai
def ms(dt):
    return int(dt.timestamp() * 1000)


def test_zai_limits_without_durations():
    buckets, plan = zai.parse_limits({"data": {"planName": "GLM Coding Pro", "limits": [
        {"type": "TIME_LIMIT", "percentage": 10, "nextResetTime": ms(NOW + timedelta(days=20))},
        {"type": "TOKENS_LIMIT", "percentage": 12, "nextResetTime": ms(NOW + timedelta(days=3))},
        {"type": "TOKENS_LIMIT", "percentage": 35, "nextResetTime": ms(NOW + timedelta(hours=2))}]}}, NOW)
    assert [(b.win, round(b.frac, 2)) for b in buckets] == [("5h", 0.35), ("7d", 0.12)]
    assert plan == "GLM Coding Pro"


def test_zai_limits_with_unit_and_counts():
    buckets, _ = zai.parse_limits({"limits": [
        {"type": "TOKENS_LIMIT", "unit": "HOUR", "number": 5, "usage": 200, "currentValue": 50,
         "nextResetTime": ms(NOW + timedelta(hours=4))}]}, NOW)
    assert (buckets[0].win, buckets[0].frac, buckets[0].window_s) == ("5h", pytest.approx(0.25), 5 * 3600)


def test_zai_key_from_claude_settings(tmp_path, monkeypatch):
    for var in ("Z_AI_API_KEY", "ZAI_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "settings.json").write_text(json.dumps({"env": {
        "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic", "ANTHROPIC_AUTH_TOKEN": "glm-key"}}))
    monkeypatch.setattr(zai, "claude_dir", lambda: tmp_path)
    assert zai.find_key() == "glm-key"
    monkeypatch.setenv("Z_AI_API_KEY", "direct")
    assert zai.find_key() == "direct"
