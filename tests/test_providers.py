import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from improvequotaia.providers import antigravity, claude, codex
from improvequotaia.providers.base import ProviderError, window_id

# Réponse réelle de `agy -p /usage --output-format json` (novembre 2026)
AGY_SAMPLE = {
    "status": "SUCCESS",
    "command": {"name": "usage", "data": {"groups": [
        {"name": "Gemini Models", "description": "Gemini Flash, Gemini Pro", "buckets": [
            {"id": "gemini-weekly", "window": "weekly", "remaining_fraction": 1, "reset_time": "2026-11-14T10:52:08Z"},
            {"id": "gemini-5h", "window": "5h", "remaining_fraction": 0.75, "reset_time": "2026-11-07T15:52:08Z"}]},
        {"name": "Claude and GPT models", "buckets": [
            {"id": "3p-weekly", "window": "weekly", "remaining_fraction": 0, "reset_time": "2026-11-10T17:00:29Z"},
            {"id": "3p-5h", "window": "5h", "disabled": True, "remaining_fraction": 1}]},
        {"name": "Gemini 4 Argon", "buckets": [
            {"id": "gemini-argon-wtu-weekly", "window": "weekly", "remaining_fraction": 0.93,
             "reset_time": "2026-11-14T10:52:08Z"}]},
    ]}},
}


def test_antigravity_parse():
    buckets = antigravity.parse_usage(AGY_SAMPLE)
    by_key = {b.key: b for b in buckets}
    assert [b.win for b in buckets if b.group == "ag-gemini"] == ["5h", "7d"]  # 5 h d'abord
    assert by_key["gemini-5h"].frac == pytest.approx(0.25)
    assert by_key["3p-weekly"].frac == pytest.approx(1.0)
    assert by_key["3p-5h"].disabled and by_key["3p-5h"].reset_at is None
    argon = [b for b in buckets if b.group == "ag-argon"]
    assert argon[0].key.endswith("5h-absent") and argon[0].disabled  # ligne « pas de limite 5 h »
    assert argon[1].frac == pytest.approx(0.07)


def test_antigravity_group_names_are_stable():
    assert antigravity.group_for("Gemini 5 Argon")[0] == "ag-argon"
    assert antigravity.group_for("Claude and GPT models")[0] == "ag-3p"
    assert antigravity.group_for("Gemini Models")[0] == "ag-gemini"
    assert antigravity.group_for("Brand New Thing")[0] == "ag-brand-new-thing"


def test_antigravity_error_status():
    with pytest.raises(ProviderError):
        antigravity.parse_usage({"status": "ERROR", "response": "boom"})


def test_window_id():
    assert window_id(299) == "5h" and window_id(10079) == "7d" and window_id(60) == "60m"


def test_codex_session_files(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    day = datetime.now()
    folder = tmp_path / "sessions" / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}"
    folder.mkdir(parents=True)
    stamp = datetime.now(timezone.utc).replace(microsecond=0)
    event = {"timestamp": stamp.isoformat().replace("+00:00", "Z"), "type": "event_msg", "payload": {
        "type": "token_count", "info": {"total_token_usage": {"total_tokens": 10}},
        "rate_limits": {"primary": {"used_percent": 40.0, "window_minutes": 299, "resets_in_seconds": 3600},
                        "secondary": {"used_percent": 22.0, "window_minutes": 10079, "resets_in_seconds": 351406}}}}
    lines = [json.dumps({"type": "session_meta"}), json.dumps(event), json.dumps({"type": "other"})]
    (folder / "rollout-test.jsonl").write_text("\n".join(lines) + "\n")

    result = codex.CodexProvider().fetch()
    primary, secondary = result.buckets
    assert (primary.win, primary.frac) == ("5h", pytest.approx(0.40))
    assert primary.reset_at == stamp + timedelta(seconds=3600)
    assert (secondary.win, secondary.frac) == ("7d", pytest.approx(0.22))
    assert secondary.window_s == 10079 * 60


def test_codex_without_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "sessions").mkdir()
    with pytest.raises(ProviderError):
        codex.CodexProvider().fetch()


def test_claude_statusline_cache(tmp_path, monkeypatch):
    cache = tmp_path / "claude_statusline.json"
    cache.write_text(json.dumps({
        "saved_at": time.time(), "model": "Opus 5.5", "effort": {"level": "xhigh"},
        "rate_limits": {"five_hour": {"used_percentage": 45, "resets_at": 1794058800},
                        "seven_day": {"used_percentage": 31, "resets_at": 1794294000}}}))
    monkeypatch.setattr(claude, "claude_statusline_cache", lambda: cache)
    monkeypatch.setattr(claude, "claude_dir", lambda: tmp_path / "no-claude")
    provider = claude.ClaudeProvider()
    result = provider.fetch()  # l'API échoue (pas d'identifiants) mais le cache suffit
    five, week = result.buckets
    assert five.frac == pytest.approx(0.45) and week.frac == pytest.approx(0.31)
    assert five.reset_at == datetime.fromtimestamp(1794058800, timezone.utc)
    assert result.source == "Claude Code"
    assert "Opus 5.5 (xhigh)" in result.title_extra


def test_antigravity_polls_fast_only_when_in_use(monkeypatch):
    provider = antigravity.AntigravityProvider()
    monkeypatch.setattr(antigravity, "agy_in_use", lambda: True)
    assert provider.interval == antigravity.ACTIVE_INTERVAL == 10.0
    monkeypatch.setattr(antigravity, "agy_in_use", lambda: False)
    assert provider.interval == antigravity.IDLE_INTERVAL == 120.0


def test_claude_parse_usage_scoped_model_limits():
    data = {
        "five_hour": {"utilization": 1.0, "resets_at": "2026-11-10T16:50:00+00:00"},
        "seven_day": {"utilization": 12.0, "resets_at": "2026-11-17T07:00:00+00:00"},
        "seven_day_opus": None,
        "seven_day_sonnet": {"utilization": 20.0, "resets_at": "2026-11-17T07:00:00+00:00"},
        "limits": [
            {"kind": "session", "group": "session", "percent": 1, "scope": None},
            {"kind": "weekly_all", "group": "weekly", "percent": 12, "scope": None},
            {"kind": "weekly_scoped", "group": "weekly", "percent": 30, "resets_at": "2026-11-17T07:00:00+00:00",
             "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None}},
            {"kind": "weekly_scoped", "group": "weekly", "percent": 25,
             "scope": {"model": {"display_name": "Sonnet"}}},
        ],
        "weekly_scoped_shares": [{"limit_index": 2, "used_percent_of_weekly": 15, "allowance_percent_of_weekly": 50}],
    }
    main, scoped = claude.parse_usage(data)
    assert [b.win for b in main] == ["5h", "7d"]
    assert main[1].frac == pytest.approx(0.12)
    fable, sonnet = scoped  # l'ancien champ seven_day_sonnet ne crée pas de doublon
    assert (fable.win, fable.win_label, fable.window_s) == ("7d", "Fable", 7 * 86400)
    assert fable.frac == pytest.approx(0.30) and not fable.disabled
    assert fable.reset_at == datetime(2026, 11, 17, 7, tzinfo=timezone.utc)
    assert "50" in fable.tooltip and "Fable" in fable.tooltip
    assert fable.key == "scoped/weekly/fable" and fable.group == "claude-code"
    assert sonnet.frac == pytest.approx(0.25) and sonnet.tooltip is None


def test_claude_parse_usage_legacy_fields_only():
    main, scoped = claude.parse_usage({"five_hour": None, "seven_day": None,
                                       "seven_day_opus": {"utilization": 40.0, "resets_at": None}})
    assert all(b.disabled for b in main)
    assert [(b.win, b.win_label, b.frac) for b in scoped] == [("7d", "Opus", pytest.approx(0.4))]
