"""Status line de Claude Code : enregistre les quotas (rate_limits) pour ImproveQuotaIa.

Claude Code appelle cette commande à chaque rafraîchissement de sa barre d'état et lui envoie un JSON
sur l'entrée standard. Ce JSON contient `rate_limits` (5 h / 7 j), issu des en-têtes des réponses de
l'API : aucune requête supplémentaire. Volontairement léger : pas de Qt, démarrage rapide.

Si l'utilisateur avait déjà sa propre status line, elle est rappelée (« chaînage ») et c'est son
texte qui s'affiche dans Claude Code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

from .config import load_config
from .paths import claude_statusline_cache


def save_cache(data: dict) -> None:
    limits = data.get("rate_limits")
    if not isinstance(limits, dict) or not limits:
        return
    path = claude_statusline_cache()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"saved_at": time.time(), "rate_limits": limits,
                   "model": (data.get("model") or {}).get("display_name"),
                   "effort": data.get("effort")}, f)
    os.replace(tmp, path)


def default_line(data: dict) -> str:
    parts = []
    model = (data.get("model") or {}).get("display_name")
    if model:
        parts.append(model)
    limits = data.get("rate_limits") or {}
    for key, name in (("five_hour", "5h"), ("seven_day", "7d")):
        pct = (limits.get(key) or {}).get("used_percentage")
        if pct is not None:
            parts.append(f"{name} {pct:.0f}%")
    return " · ".join(parts)


def main() -> None:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except ValueError:
        data = {}
    if isinstance(data, dict):
        try:
            save_cache(data)
        except OSError:
            pass
    chain = load_config().get("statusline_chain")
    if chain:
        try:
            out = subprocess.run(chain, shell=True, input=raw, capture_output=True, text=True, timeout=10)
            sys.stdout.write(out.stdout)
            return
        except (OSError, subprocess.SubprocessError):
            pass
    print(default_line(data if isinstance(data, dict) else {}))


if __name__ == "__main__":
    main()
