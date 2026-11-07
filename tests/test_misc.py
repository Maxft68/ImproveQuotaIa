import io
import json
import re
from pathlib import Path

import pytest

from improvequotaia import config, i18n, statusline

SRC = Path(__file__).resolve().parents[1] / "src" / "improvequotaia"
DYNAMIC = {  # familles de clés construites dynamiquement dans le code
    "verdict.": ["up", "ok", "down", "slow", "out", "none"],
    "advice.": ["up", "ok", "down", "slow", "out"],
    "corner.": ["top-right", "bottom-right", "bottom-left", "top-left"],
    "display.": ["hud", "tray", "main"],
    "sl.": ["ours", "none", "other", "error"],
    "win.": ["5h", "7d", "1d", "1mo"],
    "winshort.": ["5h", "7d", "1d", "1mo"],
}


def used_keys():
    keys = set()
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        keys |= set(re.findall(r"""\bt\(\s*["']([a-z0-9_]+\.[a-z0-9_.\-]+)["']""", text))
    for prefix, suffixes in DYNAMIC.items():
        keys |= {prefix + s for s in suffixes}
    return keys


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_key_is_translated(lang):
    missing = sorted(k for k in used_keys() if k not in i18n.STRINGS[lang])
    assert not missing, f"clés manquantes ({lang}) : {missing}"


def test_languages_have_same_keys():
    assert set(i18n.STRINGS["fr"]) == set(i18n.STRINGS["en"])


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    cfg = config.load_config()
    assert cfg["hud"] is True and cfg["hidden"]["hud"] == []
    cfg["hidden"]["hud"] = ["vram", "5h"]
    cfg["providers"]["codex"] = False
    config.save_config(cfg)
    again = config.load_config()
    assert again["hidden"]["hud"] == ["vram", "5h"] and again["providers"] == {"codex": False}
    assert not config.is_shown(again, "hud", "vram")
    assert not config.is_shown(again, "hud", "claude-code", "5h")
    assert config.is_shown(again, "hud", "claude-code", "7d")
    assert config.is_shown(again, "tray", "vram")


def test_corrupted_config_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    (tmp_path / "config.json").write_text("{not json")
    assert config.load_config()["opacity"] == config.DEFAULTS["opacity"]


def test_statusline_writes_cache(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "cache.json"
    monkeypatch.setattr(statusline, "claude_statusline_cache", lambda: cache)
    monkeypatch.setattr(statusline, "load_config", lambda: {"statusline_chain": None})
    payload = {"model": {"display_name": "Opus 5.5"}, "effort": {"level": "high"},
               "rate_limits": {"five_hour": {"used_percentage": 12, "resets_at": 1},
                               "seven_day": {"used_percentage": 34, "resets_at": 2}}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    statusline.main()
    saved = json.loads(cache.read_text())
    assert saved["rate_limits"]["five_hour"]["used_percentage"] == 12
    assert saved["model"] == "Opus 5.5"
    assert capsys.readouterr().out.strip() == "Opus 5.5 · 5h 12% · 7d 34%"
