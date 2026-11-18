"""Claude Code (abonnement Pro / Max) : quotas 5 h et 7 jours.

Deux sources, on garde la plus récente :
  1. le cache écrit par la status line de Claude Code (improvequotaia.statusline), lu à chaque passage :
     gratuit, en direct, issu des en-têtes des réponses de l'API ;
  2. l'interface OAuth /api/oauth/usage (celle de la commande /usage), au plus toutes les 5 min :
     elle répond 429 si on l'appelle plus souvent. Elle voit aussi l'usage de claude.ai.

Les quotas propres à un modèle (ex. Fable) ne viennent que de l'API : entrées `weekly_scoped` du
tableau `limits` (et, pour les anciens comptes, `seven_day_opus` / `seven_day_sonnet`).

Identifiants : ~/.claude/.credentials.json (Linux, Windows) ou trousseau macOS.
Ils ne sont envoyés qu'au serveur d'Anthropic.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..i18n import t
from ..paths import claude_dir, claude_json, claude_statusline_cache
from ..utils import parse_time, run_quiet
from .base import FIVE_H, WEEK, Bucket, Provider, ProviderError, ProviderResult, ToolMissing

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
API_INTERVAL_S = 300
GROUP = ("claude-code", "Claude Code")
SCOPED_WINDOWS = {"session": ("5h", FIVE_H), "weekly": ("7d", WEEK)}
LEGACY_SCOPED = (("seven_day_opus", "Opus"), ("seven_day_sonnet", "Sonnet"))


class RateLimited(ProviderError):
    def __init__(self, retry_after: int):
        super().__init__(t("err.rate_limited", s=retry_after))
        self.retry_after = retry_after


def _claude_cli_path() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / "bin" / "claude",
        Path("/usr/local/bin/claude"),
    ]
    for p in candidates:
        if p.exists() and os.access(p, os.X_OK):
            return str(p)
    return None


def _save_credentials(oauth_data: dict) -> None:
    path = claude_dir() / ".credentials.json"
    try:
        root = {}
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    root = json.load(f)
            except (ValueError, OSError):
                root = {}
        if not isinstance(root, dict):
            root = {}
        root["claudeAiOauth"] = oauth_data
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(root, f, indent=2)
            f.write("\n")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except OSError:
        pass


def refresh_credentials(creds: dict) -> dict:
    cli = _claude_cli_path()
    if cli:
        try:
            r = run_quiet([cli, "auth", "status"], timeout=15)
            if r.returncode == 0:
                new_creds = read_credentials()
                new_exp = (new_creds.get("expiresAt") or 0) / 1000
                if new_exp > time.time():
                    return new_creds
        except Exception:
            pass

    refresh_tok = creds.get("refreshToken")
    if not refresh_tok:
        return creds

    scopes = creds.get("scopes") or ["user:profile", "user:inference", "user:sessions:claude_code"]
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
        "client_id": OAUTH_CLIENT_ID,
        "scope": " ".join(scopes) if isinstance(scopes, list) else str(scopes),
    }
    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "improvequotaia"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        if isinstance(data, dict) and data.get("access_token"):
            creds["accessToken"] = data["access_token"]
            if data.get("refresh_token"):
                creds["refreshToken"] = data["refresh_token"]
            expires_in = data.get("expires_in", 28800)
            creds["expiresAt"] = int((time.time() + expires_in) * 1000)
            _save_credentials(creds)
            return creds
    except Exception:
        pass
    return creds


def read_credentials() -> dict:
    path = claude_dir() / ".credentials.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["claudeAiOauth"]
    except FileNotFoundError:
        pass
    except (ValueError, KeyError):
        raise ProviderError(t("err.claude_creds_unreadable"))
    if sys.platform == "darwin":
        try:
            r = run_quiet(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"], timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return json.loads(r.stdout.strip())["claudeAiOauth"]
        except (OSError, ValueError, KeyError):
            pass
    raise ToolMissing(t("err.claude_not_logged"))


def _bucket(key, win, window_s, frac, reset_at, tooltip=None, win_label=None):
    return Bucket(key=key, group=GROUP[0], group_label=GROUP[1], win=win, frac=frac, reset_at=reset_at,
                  window_s=window_s, disabled=frac is None, note="—" if frac is None else None,
                  tooltip=tooltip, win_label=win_label)


def _scope_label(scope) -> str | None:
    """Nom affiché d'une limite ciblée : le modèle (ex. « Fable »), sinon la surface."""
    if not isinstance(scope, dict):
        return None
    for part in (scope.get("model"), scope.get("surface")):
        if isinstance(part, dict) and (part.get("display_name") or part.get("id")):
            return str(part.get("display_name") or part.get("id"))
        if isinstance(part, str) and part:
            return part
    return None


def parse_usage(data: dict):
    """Réponse de /api/oauth/usage -> (lignes 5 h / 7 j, lignes par modèle). Fonction pure, testée."""
    def row(key, win, secs):
        b = data.get(key)
        if not isinstance(b, dict) or b.get("utilization") is None:
            return None
        return _bucket(key, win, secs, b["utilization"] / 100.0, parse_time(b.get("resets_at")),
                       b.get("locked_reason"))

    main = [row("five_hour", "5h", FIVE_H) or _bucket("five_hour", "5h", FIVE_H, None, None),
            row("seven_day", "7d", WEEK) or _bucket("seven_day", "7d", WEEK, None, None)]

    shares = {s.get("limit_index"): s.get("allowance_percent_of_weekly")
              for s in data.get("weekly_scoped_shares") or [] if isinstance(s, dict)}
    scoped, seen = [], set()
    limits = data.get("limits") if isinstance(data.get("limits"), list) else []
    for i, lim in enumerate(limits):
        if not isinstance(lim, dict) or not lim.get("scope") or lim.get("percent") is None:
            continue
        label = _scope_label(lim["scope"])
        win_secs = SCOPED_WINDOWS.get(lim.get("group"))
        if not label or not win_secs or (label, win_secs[0]) in seen:
            continue
        seen.add((label, win_secs[0]))
        share = shares.get(i)
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        scoped.append(_bucket(f"scoped/{lim.get('group')}/{slug}", win_secs[0], win_secs[1],
                              float(lim["percent"]) / 100.0, parse_time(lim.get("resets_at")),
                              t("tip.claude_share", pct=f"{share:g}", model=label)
                              if isinstance(share, (int, float)) else None,
                              win_label=label))
    for key, label in LEGACY_SCOPED:
        b = data.get(key)
        if (label, "7d") in seen or not isinstance(b, dict) or b.get("utilization") is None:
            continue
        scoped.append(_bucket(key, "7d", WEEK, b["utilization"] / 100.0, parse_time(b.get("resets_at")),
                              b.get("locked_reason"), win_label=label))
    return main, scoped


class ClaudeProvider(Provider):
    id = "claude"
    label = "Claude Code"
    title = "CLAUDE"
    groups = [GROUP]

    def __init__(self):
        self.plan = self.model = self.effort = None
        self.best, self.best_at, self.source = None, 0.0, None
        self.optional = []
        self.next_api = 0.0
        self.consecutive_429 = 0
        self.api_error = None

    def detect(self) -> bool:
        return (claude_dir() / ".credentials.json").exists() or _claude_cli_path() is not None \
            or claude_statusline_cache().exists() or claude_json().exists()

    def _from_claude_json(self):
        try:
            path = claude_json()
            if not path.exists():
                return None
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            cached = data.get("cachedUsageUtilization")
            if not isinstance(cached, dict):
                return None
            saved_at = float(cached.get("fetchedAtMs") or 0) / 1000.0
            util = cached.get("utilization")
            if not isinstance(util, dict) or saved_at <= self.best_at:
                return None
            main, scoped = parse_usage(util)
            return saved_at, main, scoped
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _from_statusline(self):
        try:
            with open(claude_statusline_cache(), encoding="utf-8") as f:
                cache = json.load(f)
            saved_at, limits = float(cache["saved_at"]), cache["rate_limits"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        self.model = cache.get("model") or self.model
        effort = cache.get("effort")
        self.effort = (effort.get("level") if isinstance(effort, dict) else effort) or self.effort
        if saved_at <= self.best_at:
            return None
        buckets = []
        for key, win, secs in (("five_hour", "5h", FIVE_H), ("seven_day", "7d", WEEK)):
            b = limits.get(key) or {}
            pct = b.get("used_percentage")
            buckets.append(_bucket(key, win, secs, None if pct is None else pct / 100.0,
                                   parse_time(b.get("resets_at"))))
        return saved_at, buckets

    def _from_api(self, retried: bool = False):
        creds = read_credentials()
        self.plan = creds.get("subscriptionType") or self.plan
        expires = (creds.get("expiresAt") or 0) / 1000
        if expires and expires <= time.time() + 60:
            creds = refresh_credentials(creds)
            self.plan = creds.get("subscriptionType") or self.plan
            expires = (creds.get("expiresAt") or 0) / 1000
        if expires and expires < time.time():
            raise ProviderError(t("err.claude_token_expired"))
        req = urllib.request.Request(USAGE_URL, headers={
            "Authorization": "Bearer " + creds["accessToken"],
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "improvequotaia",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 401 and not retried:
                creds = refresh_credentials(creds)
                return self._from_api(retried=True)
            if e.code == 429:
                self.consecutive_429 += 1
                retry = e.headers.get("Retry-After", "")
                raise RateLimited(int(retry) if retry.isdigit()
                                  else min(1800, API_INTERVAL_S * 2 ** self.consecutive_429))
            if e.code in (401, 403):
                raise ProviderError(t("err.claude_token_refused"))
            raise ProviderError(t("err.http", code=e.code))
        except urllib.error.URLError as e:
            raise ProviderError(t("err.network", reason=e.reason))
        except (TimeoutError, ValueError) as e:
            raise ProviderError(t("err.invalid_response", detail=e))
        self.consecutive_429 = 0
        if not isinstance(data, dict):
            raise ProviderError(t("err.invalid_response", detail=type(data).__name__))
        main, self.optional = parse_usage(data)
        return main

    def fetch(self) -> ProviderResult:
        sl = self._from_statusline()
        if sl:
            self.best_at, self.best, self.source = sl[0], sl[1], "Claude Code"
        cj = self._from_claude_json()
        if cj and cj[0] > self.best_at:
            self.best_at, self.best, self.optional, self.source = cj[0], cj[1], cj[2], "Claude Code"
        now = time.time()
        if now >= self.next_api:
            try:
                rows = self._from_api()
                self.best_at, self.best, self.source = now, rows, "API"
                self.api_error = None
                self.next_api = now + API_INTERVAL_S
            except RateLimited as e:
                self.api_error, self.next_api = f"API : {e}", now + e.retry_after
            except ProviderError as e:
                self.api_error, self.next_api = f"API : {e}", now + 60
                if isinstance(e, ToolMissing) and self.best is None and not claude_statusline_cache().exists() and not claude_json().exists():
                    raise
        if self.best is None:
            raise ProviderError(self.api_error or t("err.waiting"))
        extra = " · ".join(x for x in (
            self.plan.capitalize() if self.plan else None,
            (self.model + (f" ({self.effort})" if self.effort else "")) if self.model else None,
        ) if x)
        return ProviderResult(self.best + self.optional, self.best_at, self.source, self.api_error, extra or None)
