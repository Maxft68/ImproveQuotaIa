"""Utilitaires communs : sous-processus discrets, dates, durées."""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Sequence

from .i18n import t

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW : pas de console qui clignote


def run_quiet(cmd: Sequence[str], timeout: float = 30, input_text: Optional[str] = None,
              cwd: Optional[str] = None, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    kwargs = dict(capture_output=True, text=True, encoding="utf-8", errors="replace",
                  timeout=timeout, cwd=cwd, env=env)
    if input_text is None:
        kwargs["stdin"] = subprocess.DEVNULL
    else:
        kwargs["input"] = input_text
    if _NO_WINDOW:
        kwargs["creationflags"] = _NO_WINDOW
    return subprocess.run(list(cmd), **kwargs)


def popen_quiet(cmd: Sequence[str]) -> subprocess.Popen:
    kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                  text=True, encoding="utf-8", errors="replace")
    if _NO_WINDOW:
        kwargs["creationflags"] = _NO_WINDOW
    return subprocess.Popen(list(cmd), **kwargs)


def parse_time(value) -> Optional[datetime]:
    """ISO 8601 (avec « Z » accepté dès Python 3.9) ou horodatage Unix (s ou ms)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fnum(text) -> Optional[float]:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def fmt_left(dt: datetime) -> str:
    secs = (dt - datetime.now(timezone.utc)).total_seconds()
    if secs <= 0:
        return t("time.now")
    mins = int(secs // 60)
    days, mins = divmod(mins, 1440)
    hours, mins = divmod(mins, 60)
    if days:
        return t("time.dh", d=days, h=hours)
    if hours:
        return t("time.hm", h=hours, m=f"{mins:02d}")
    return t("time.m", m=max(mins, 1))


def fmt_abs(dt: datetime) -> str:
    return dt.astimezone().strftime("%a %d %b %H:%M")


def fmt_ago(ts: float) -> str:
    secs = int(time.time() - ts)
    if secs < 60:
        return t("ago.s", n=max(secs, 0))
    if secs < 3600:
        return t("ago.m", n=secs // 60)
    return t("ago.h", n=secs // 3600)
