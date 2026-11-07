"""Textes de l'interface (français / anglais). La langue suit le système, sauf choix explicite."""
from __future__ import annotations

import locale
import os

STRINGS = {
    "fr": {
        "verdict.up": "monte", "verdict.ok": "garde", "verdict.down": "baisse",
        "verdict.slow": "ralentis", "verdict.out": "épuisé", "verdict.none": "—",
        "advice.up": "Barre derrière le trait : tu peux monter de modèle ou d'effort.",
        "advice.ok": "Rythme tenable : garde ton modèle et ton effort actuels.",
        "advice.down": "Barre un peu devant le trait : baisse le modèle ou l'effort.",
        "advice.slow": "Barre loin devant le trait : modèle léger, effort bas, ou fais une pause.",
        "advice.out": "Quota épuisé jusqu'à la réinitialisation.",
        "pace.detail": "{used} % consommé / {elapsed} % du temps écoulé (barre {gap} pts {where})",
        "pace.behind": "derrière le trait", "pace.ahead": "devant le trait",
        "win.5h": "5 h", "win.7d": "Semaine", "win.1d": "Jour",
        "win.5h_long": "Fenêtre 5 h", "win.7d_long": "Fenêtre 7 jours",
        "time.now": "maintenant", "time.dh": "{d}j {h}h", "time.hm": "{h}h{m}", "time.m": "{m} min",
        "ago.s": "il y a {n} s", "ago.m": "il y a {n} min", "ago.h": "il y a {n} h",
        "reset.in": "dans {left}", "tip.reset": "Réinitialisation : {when}",
        "tip.cores": "{n} cœurs logiques", "unit.gb": "Go", "gpu.waiting": "en attente…",
        "note.disabled": "désactivé", "note.no_5h": "pas de limite 5 h", "note.reset_done": "réinitialisé",
        "tip.no_5h": "L'outil ne renvoie pas de limite 5 h pour ce groupe (seule la limite hebdomadaire s'applique).",
        "section.system": "SYSTÈME", "status.every_second": "chaque seconde",
        "status.loading": "chargement…", "status.updated": "maj {ago}",
        "panel.empty": "Rien à afficher : choisis les éléments dans « Affichage ».",
        "main.hud_tip": "HUD translucide, toujours visible et traversé par la souris",
        "main.settings": "Affichage…", "main.refresh": "Rafraîchir",
        "main.legend": "Barre = tokens consommés · trait blanc = temps écoulé dans la fenêtre (5 h ou 7 j). "
                       "Barre derrière le trait → tu peux monter de modèle/effort ; "
                       "barre devant le trait → baisse ou ralentis.",
        "tray.legend": "↑ monte   → garde   ↓ baisse   ⇊ ralentis   ✕ épuisé",
        "tray.open": "Ouvrir la fenêtre", "tray.settings": "Affichage et réglages…",
        "tray.hud": "Afficher le HUD", "tray.corner": "Position du HUD", "tray.opacity": "Opacité du HUD",
        "tray.refresh": "Rafraîchir les quotas", "tray.quit": "Quitter",
        "tray.back_in": "retour dans {left}", "tray.no_data": "En attente des quotas…",
        "corner.top-right": "En haut à droite", "corner.bottom-right": "En bas à droite",
        "corner.bottom-left": "En bas à gauche", "corner.top-left": "En haut à gauche",
        "display.hud": "HUD", "display.tray": "Icône", "display.main": "Fenêtre",
        "settings.title": "Réglages", "settings.tab_display": "Affichage", "settings.tab_tools": "Outils",
        "settings.tab_general": "Général", "settings.quotas": "Quotas", "settings.windows": "Fenêtres de quota",
        "settings.display_note": "Les changements s'appliquent immédiatement. Une section dont l'outil n'est "
                                 "pas installé est masquée automatiquement.",
        "tools.detected": "détecté sur cet ordinateur", "tools.not_found": "non trouvé",
        "tools.experimental": "expérimental",
        "sl.title": "Quotas Claude en direct",
        "sl.explain": "Sans cette option, les quotas Claude ne sont relevés que toutes les 5 minutes. Avec, Claude Code "
                      "les transmet à ImproveQuotaIa à chaque message. Rien à faire à la main : ImproveQuotaIa règle "
                      "Claude Code tout seul (une sauvegarde de ses réglages est faite).",
        "sl.ours": "Activé ✓", "sl.none": "Désactivé (quotas relevés toutes les 5 min)",
        "sl.other": "Tu as déjà ta propre barre d'état dans Claude Code : elle restera affichée.",
        "sl.error": "Les réglages de Claude Code sont illisibles : rien n'a été modifié.",
        "sl.install": "Activer", "sl.uninstall": "Désactiver",
        "sl.failed": "Impossible de modifier les réglages de Claude Code : {err}",
        "general.language": "Langue", "general.restart_note": "Prise en compte au prochain démarrage.",
        "general.autostart": "Démarrer avec l'ordinateur", "lang.auto": "Automatique",
        "wizard.title": "Bienvenue dans {app}",
        "wizard.intro": "Coche les outils dont tu veux suivre les quotas. Ceux trouvés sur cet ordinateur "
                        "sont déjà cochés. Tu pourras tout changer plus tard dans « Affichage et réglages ».",
        "wizard.options": "OPTIONS", "wizard.system": "Afficher aussi CPU / GPU / RAM",
        "wizard.hud": "Afficher le HUD translucide (toujours visible, traversé par la souris)",
        "wizard.statusline": "Quotas Claude en direct (recommandé)",
        "wizard.privacy": "Aucune clé API à saisir : ImproveQuotaIa réutilise les connexions déjà présentes sur cet "
                          "ordinateur et n'envoie rien à un serveur tiers.",
        "wizard.finish": "Terminer",
        "err.agy_missing": "agy introuvable", "err.agy_timeout": "agy ne répond pas",
        "err.agy_unreadable": "réponse d'agy illisible",
        "err.claude_not_logged": "non connecté à Claude Code",
        "err.claude_creds_unreadable": "identifiants Claude illisibles",
        "err.claude_token_expired": "jeton expiré : ouvre Claude Code pour le rafraîchir",
        "err.claude_token_refused": "jeton refusé : relance Claude Code",
        "err.rate_limited": "limité par l'API, nouvel essai dans {s} s",
        "err.http": "erreur HTTP {code}", "err.network": "réseau : {reason}",
        "err.invalid_response": "réponse invalide : {detail}", "err.waiting": "en attente de données",
        "err.codex_missing": "Codex introuvable",
        "err.codex_no_data": "aucun quota dans les sessions Codex récentes (envoie un message à Codex)",
        "err.autostart": "Impossible de régler le démarrage automatique : {err}",
        "demo.activities": "Activités",
        "settings.tab_about": "À propos", "about.by": "Créé par {author}",
        "about.source": "Code source et nouveautés", "about.issues": "Signaler un problème ou proposer une idée",
        "about.license": "Logiciel libre et gratuit, sous licence GNU GPL v3.",
        "about.support": "SOUTENIR LE PROJET",
        "about.donate_note": "ImproveQuotaIa est gratuit. S'il t'aide à mieux utiliser tes quotas, tu peux m'offrir "
                             "un chocolat chaud : sans inscription, par carte ou PayPal.",
        "about.donate": "Paye-moi un chocolat chaud",
        "winshort.5h": "5h", "winshort.7d": "7j", "winshort.1d": "1j", "winshort.1mo": "mois",
        "provider.antigravity": "Antigravity (Google AI Pro / Ultra : Gemini, Argon, Claude)",
        "provider.gemini-cli": "Gemini CLI (comptes Google Code Assist entreprise)",
        "wizard.menu_shortcut": "Ajouter ImproveQuotaIa au menu des applications",
        "wizard.desktop_shortcut": "Créer un raccourci sur le bureau",
        "wizard.relaunch_note": "Pour relancer ImproveQuotaIa après l'avoir quitté (utile si le démarrage automatique est décoché).",
        "wizard.statusline_ours": "Déjà activé ✓ — décoche pour désactiver.",
        "wizard.statusline_disabled": "Coche d'abord Claude Code pour activer cette option.",
        "general.menu_shortcut": "Raccourci dans le menu des applications",
        "general.desktop_shortcut": "Raccourci sur le bureau",
        "general.tray_text": "Texte dans la barre du haut (ex. « Claude 5h↓ 7j↑ »)",
        "shortcut.comment": "Rythme de consommation des quotas IA + CPU/GPU/RAM",
        "err.shortcut": "Impossible de créer le raccourci : {err}",
        "win.1mo": "Mois", "win.1d_long": "Fenêtre 1 jour", "win.1mo_long": "Fenêtre 1 mois",
        "err.grok_missing": "non connecté à Grok (lance « grok login »)",
        "err.grok_token_expired": "jeton Grok expiré ou refusé : relance le CLI Grok",
        "err.grok_no_data": "réponse de facturation Grok sans pourcentage d'utilisation",
        "err.copilot_missing": "aucun jeton GitHub Copilot trouvé (connecte-toi avec « gh auth login »)",
        "err.copilot_ended": "abonnement Copilot terminé",
        "err.copilot_no_quota": "aucun quota limité (offre illimitée)",
        "err.gemini_cli_missing": "Gemini CLI n'est pas connecté avec un compte Google",
        "err.gemini_cli_expired": "jeton Gemini expiré : relance Gemini CLI",
        "err.gemini_cli_no_data": "aucun quota renvoyé par Google",
        "err.gemini_consumer": "Google ne fournit plus ce quota aux comptes individuels : suis la section Antigravity",
        "err.zai_missing": "aucune clé z.ai trouvée",
        "err.zai_key_refused": "clé z.ai refusée",
        "err.zai_no_data": "aucun quota de jetons dans la réponse z.ai",
    },
    "en": {
        "verdict.up": "go up", "verdict.ok": "keep", "verdict.down": "lower",
        "verdict.slow": "slow down", "verdict.out": "used up", "verdict.none": "—",
        "advice.up": "Bar behind the marker: you can use a bigger model or more effort.",
        "advice.ok": "Sustainable pace: keep your current model and effort.",
        "advice.down": "Bar slightly ahead of the marker: lower the model or the effort.",
        "advice.slow": "Bar far ahead of the marker: lighter model, low effort, or take a break.",
        "advice.out": "Quota used up until the reset.",
        "pace.detail": "{used}% used / {elapsed}% of time elapsed (bar {gap} pts {where})",
        "pace.behind": "behind the marker", "pace.ahead": "ahead of the marker",
        "win.5h": "5 h", "win.7d": "Week", "win.1d": "Day",
        "win.5h_long": "5-hour window", "win.7d_long": "7-day window",
        "time.now": "now", "time.dh": "{d}d {h}h", "time.hm": "{h}h{m}", "time.m": "{m} min",
        "ago.s": "{n}s ago", "ago.m": "{n} min ago", "ago.h": "{n}h ago",
        "reset.in": "in {left}", "tip.reset": "Resets: {when}",
        "tip.cores": "{n} logical cores", "unit.gb": "GB", "gpu.waiting": "waiting…",
        "note.disabled": "disabled", "note.no_5h": "no 5 h limit", "note.reset_done": "reset",
        "tip.no_5h": "The tool reports no 5-hour limit for this group (only the weekly limit applies).",
        "section.system": "SYSTEM", "status.every_second": "every second",
        "status.loading": "loading…", "status.updated": "updated {ago}",
        "panel.empty": "Nothing to show: pick items in “Display”.",
        "main.hud_tip": "Translucent HUD, always visible, clicks go through it",
        "main.settings": "Display…", "main.refresh": "Refresh",
        "main.legend": "Bar = tokens used · white marker = time elapsed in the window (5 h or 7 d). "
                       "Bar behind the marker → you can go up a model/effort; "
                       "bar ahead of the marker → lower or slow down.",
        "tray.legend": "↑ go up   → keep   ↓ lower   ⇊ slow down   ✕ used up",
        "tray.open": "Open window", "tray.settings": "Display & settings…",
        "tray.hud": "Show HUD", "tray.corner": "HUD position", "tray.opacity": "HUD opacity",
        "tray.refresh": "Refresh quotas", "tray.quit": "Quit",
        "tray.back_in": "back in {left}", "tray.no_data": "Waiting for quotas…",
        "corner.top-right": "Top right", "corner.bottom-right": "Bottom right",
        "corner.bottom-left": "Bottom left", "corner.top-left": "Top left",
        "display.hud": "HUD", "display.tray": "Icon", "display.main": "Window",
        "settings.title": "Settings", "settings.tab_display": "Display", "settings.tab_tools": "Tools",
        "settings.tab_general": "General", "settings.quotas": "Quotas", "settings.windows": "Quota windows",
        "settings.display_note": "Changes apply immediately. Sections for tools that are not installed are "
                                 "hidden automatically.",
        "tools.detected": "found on this computer", "tools.not_found": "not found",
        "tools.experimental": "experimental",
        "sl.title": "Live Claude quotas",
        "sl.explain": "Without this option, Claude quotas are only checked every 5 minutes. With it, Claude Code hands "
                      "them to ImproveQuotaIa on every message. Nothing to do by hand: ImproveQuotaIa sets Claude Code "
                      "up by itself (its settings are backed up first).",
        "sl.ours": "On ✓", "sl.none": "Off (quotas checked every 5 min)",
        "sl.other": "You already have your own Claude Code status line: it stays displayed.",
        "sl.error": "Claude Code settings are unreadable: nothing was changed.",
        "sl.install": "Turn on", "sl.uninstall": "Turn off",
        "sl.failed": "Could not update Claude Code settings: {err}",
        "general.language": "Language", "general.restart_note": "Applied on next start.",
        "general.autostart": "Start with the computer", "lang.auto": "Automatic",
        "wizard.title": "Welcome to {app}",
        "wizard.intro": "Tick the tools whose quotas you want to follow. Tools found on this computer are "
                        "already ticked. You can change everything later in “Display & settings”.",
        "wizard.options": "OPTIONS", "wizard.system": "Also show CPU / GPU / RAM",
        "wizard.hud": "Show the translucent HUD (always visible, clicks go through it)",
        "wizard.statusline": "Live Claude quotas (recommended)",
        "wizard.privacy": "No API key to enter: ImproveQuotaIa reuses the sign-ins already on this computer and "
                          "sends nothing to any third-party server.",
        "wizard.finish": "Finish",
        "err.agy_missing": "agy not found", "err.agy_timeout": "agy is not responding",
        "err.agy_unreadable": "unreadable agy response",
        "err.claude_not_logged": "not signed in to Claude Code",
        "err.claude_creds_unreadable": "unreadable Claude credentials",
        "err.claude_token_expired": "token expired: open Claude Code to refresh it",
        "err.claude_token_refused": "token refused: restart Claude Code",
        "err.rate_limited": "rate limited by the API, retrying in {s}s",
        "err.http": "HTTP error {code}", "err.network": "network: {reason}",
        "err.invalid_response": "invalid response: {detail}", "err.waiting": "waiting for data",
        "err.codex_missing": "Codex not found",
        "err.codex_no_data": "no quota in recent Codex sessions (send Codex a message)",
        "err.autostart": "Could not set start-up launch: {err}",
        "demo.activities": "Activities",
        "settings.tab_about": "About", "about.by": "Made by {author}",
        "about.source": "Source code and news", "about.issues": "Report a problem or suggest an idea",
        "about.license": "Free and open-source software, licensed under the GNU GPL v3.",
        "about.support": "SUPPORT THE PROJECT",
        "about.donate_note": "ImproveQuotaIa is free. If it helps you make better use of your quotas, you can buy me "
                             "a hot chocolate: no sign-up, card or PayPal.",
        "about.donate": "Buy me a hot chocolate",
        "winshort.5h": "5h", "winshort.7d": "7d", "winshort.1d": "1d", "winshort.1mo": "mo",
        "provider.antigravity": "Antigravity (Google AI Pro / Ultra: Gemini, Argon, Claude)",
        "provider.gemini-cli": "Gemini CLI (Google Code Assist business accounts)",
        "wizard.menu_shortcut": "Add ImproveQuotaIa to the applications menu",
        "wizard.desktop_shortcut": "Create a desktop shortcut",
        "wizard.relaunch_note": "To start ImproveQuotaIa again after quitting it (useful if start-up launch is unticked).",
        "wizard.statusline_ours": "Already on ✓ — untick to turn off.",
        "wizard.statusline_disabled": "Tick Claude Code first to use this option.",
        "general.menu_shortcut": "Shortcut in the applications menu",
        "general.desktop_shortcut": "Desktop shortcut",
        "general.tray_text": "Text in the top bar (e.g. “Claude 5h↓ 7d↑”)",
        "shortcut.comment": "AI quota pace + CPU/GPU/RAM",
        "err.shortcut": "Could not create the shortcut: {err}",
        "win.1mo": "Month", "win.1d_long": "1-day window", "win.1mo_long": "1-month window",
        "err.grok_missing": "not signed in to Grok (run “grok login”)",
        "err.grok_token_expired": "Grok token expired or refused: restart the Grok CLI",
        "err.grok_no_data": "Grok billing response has no usage percentage",
        "err.copilot_missing": "no GitHub Copilot token found (sign in with “gh auth login”)",
        "err.copilot_ended": "Copilot subscription ended",
        "err.copilot_no_quota": "no limited quota (unlimited plan)",
        "err.gemini_cli_missing": "Gemini CLI is not signed in with a Google account",
        "err.gemini_cli_expired": "Gemini token expired: restart Gemini CLI",
        "err.gemini_cli_no_data": "Google returned no quota",
        "err.gemini_consumer": "Google no longer reports this quota for personal accounts: follow the Antigravity section",
        "err.zai_missing": "no z.ai key found",
        "err.zai_key_refused": "z.ai key refused",
        "err.zai_no_data": "no token quota in the z.ai response",
    },
}

_lang = None


def set_language(code) -> None:
    global _lang
    code = (code or "").lower()[:2]
    _lang = code if code in STRINGS else "en"


def language() -> str:
    if _lang:
        return _lang
    for var in ("IMPROVEQUOTAIA_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "fr" if value.lower().startswith("fr") else "en"
    try:
        loc = (locale.getlocale()[0] or "").lower()
    except ValueError:
        loc = ""
    return "fr" if loc.startswith("fr") else "en"


def provider_label(provider) -> str:
    """Nom affiché d'un outil, avec une précision traduite quand elle évite une confusion."""
    return STRINGS[language()].get(f"provider.{provider.id}") or provider.label


def t(key: str, **kwargs) -> str:
    text = STRINGS[language()].get(key) or STRINGS["en"].get(key) or key
    return text.format(**kwargs) if kwargs else text
