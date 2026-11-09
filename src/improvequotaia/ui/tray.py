"""Icône de la zone de notification.

Deux variantes, même contenu :
  - LinuxTextTray : indicateur AppIndicator avec le texte « Claude 5h↓ 7j↑ · Gemini 5h↑ 7j↑ »
    dans la barre du haut (Linux), via un petit processus séparé (improvequotaia/linux_indicator.py) ;
  - Tray : QSystemTrayIcon (macOS, Windows, et Linux sans AppIndicator) : pastilles colorées,
    le texte est dans l'infobulle et le menu.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..i18n import t
from ..pace import ARROWS, worst
from ..paths import APP_NAME, cache_dir
from ..utils import fmt_left, run_quiet
from .panel import bucket_sub, pace_detail
from .widgets import tray_pixmap

CORNERS = ("top-right", "bottom-right", "bottom-left", "top-left")
OPACITIES = (0.5, 0.7, 0.9, 1.0)
SHORT = {"Claude Code": "Claude", "Claude / GPT": "AG·Claude", "GitHub Copilot": "Copilot", "GLM (z.ai)": "GLM"}


# ---------------------------------------------------------------- contenu commun

def label_text(groups) -> str:
    """Ex. « Claude 5h↓ 7j↑ · Gemini 5h↑ 7j↑ · Argon 7j↓ · AG·Claude 7j✕ »."""
    parts = []
    for g in groups:
        if g.get("sys"):
            parts.append(f"{g['label']} {g['sys']}")
            continue
        tokens = []
        for win, b in g["wins"]:
            short = b.win_label or t(f"winshort.{win}")
            tokens.append(f"{short}{ARROWS[b.pace.verdict]}")
        parts.append(f"{SHORT.get(g['label'], g['label'])} " + " ".join(tokens))
    return " · ".join(parts)


def info_lines(groups):
    lines = []
    for g in groups:
        if g.get("info"):
            lines.append(g["info"])
            continue
        for _win, b in g["wins"]:
            v = b.pace.verdict
            detail = pace_detail(b) or (t("tray.back_in", left=fmt_left(b.reset_at)) if b.reset_at else "")
            lines.append(f"{ARROWS[v]} {g['label']} · {bucket_sub(b)} : {t('verdict.' + v)}"
                         + (f" — {detail}" if detail else ""))
    return lines


def main_verdict(groups):
    q = next((g for g in groups if g.get("wins")), None)
    return worst(b.pace.verdict for _w, b in q["wins"]) if q else None


# ---------------------------------------------------------------- indicateur avec texte (Linux)

PROBE = ("import gi\n"
         "try:\n"
         "    gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import AyatanaAppIndicator3\n"
         "except Exception:\n"
         "    gi.require_version('AppIndicator3', '0.1'); from gi.repository import AppIndicator3\n")


def indicator_script() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "improvequotaia" / "linux_indicator.py"
    return Path(__file__).resolve().parent.parent / "linux_indicator.py"


def indicator_python():
    """Python du système capable d'afficher un AppIndicator (None si indisponible)."""
    if not sys.platform.startswith("linux") or not indicator_script().exists():
        return None
    for candidate in dict.fromkeys(filter(None, ("/usr/bin/python3", shutil.which("python3")))):
        try:
            if run_quiet([candidate, "-c", PROBE], timeout=10).returncode == 0:
                return candidate
        except Exception:
            continue
    return None


class LinuxTextTray(QObject):
    def __init__(self, ctrl, python: str):
        super().__init__()
        self.ctrl = ctrl
        self.groups = []
        self.last_sent = None
        self.closing = False
        self.icon_dir = cache_dir() / "icons"
        self.icon_dir.mkdir(parents=True, exist_ok=True)
        self.proc = QProcess(self)
        self.proc.setProgram(python)
        self.proc.setArguments([str(indicator_script())])
        self.proc.readyReadStandardOutput.connect(self.on_output)
        self.proc.finished.connect(self.on_finished)
        self.proc.start()

    def _icon(self, verdict) -> str:
        name = f"improvequotaia-{verdict or 'none'}"
        path = self.icon_dir / f"{name}.png"
        if not path.exists():
            tray_pixmap([verdict] if verdict else []).save(str(path), "PNG")
        return name

    def menu_spec(self):
        cfg = self.ctrl.config
        lines = info_lines(self.groups) or [t("tray.no_data")]
        return ([{"kind": "item", "id": "open", "label": line} for line in lines] + [
            {"kind": "sep"},
            {"kind": "label", "label": t("tray.legend")},
            {"kind": "sep"},
            {"kind": "item", "id": "open", "label": t("tray.open")},
            {"kind": "item", "id": "settings", "label": t("tray.settings")},
            {"kind": "check", "id": "hud", "label": t("tray.hud"), "active": bool(cfg["hud"])},
            {"kind": "submenu", "label": t("tray.corner"), "items": [
                {"kind": "radio", "id": f"corner:{c}", "label": t(f"corner.{c}"), "active": cfg["corner"] == c}
                for c in CORNERS]},
            {"kind": "submenu", "label": t("tray.opacity"), "items": [
                {"kind": "radio", "id": f"opacity:{o}", "label": f"{o * 100:.0f} %",
                 "active": abs(cfg["opacity"] - o) < 0.01} for o in OPACITIES]},
            {"kind": "sep"},
            {"kind": "item", "id": "refresh", "label": t("tray.refresh")},
            {"kind": "item", "id": "quit", "label": t("tray.quit")},
        ])

    def update(self, groups):
        self.groups = groups
        msg = json.dumps({"label": label_text(groups), "icon": self._icon(main_verdict(groups)),
                          "icon_dir": str(self.icon_dir), "menu": self.menu_spec()}, ensure_ascii=False)
        if msg != self.last_sent and self.proc.state() == QProcess.Running:
            self.proc.write((msg + "\n").encode("utf-8"))
            self.last_sent = msg

    def sync(self, _config):
        self.update(self.groups)

    def on_output(self):
        for line in bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            item, active = event.get("id") or "", event.get("active")
            if item == "open":
                self.ctrl.show_main()
            elif item == "settings":
                self.ctrl.show_settings()
            elif item == "hud":
                self.ctrl.set_hud(bool(active))
            elif item.startswith("corner:"):
                self.ctrl.set_corner(item.split(":", 1)[1])
            elif item.startswith("opacity:"):
                self.ctrl.set_opacity(float(item.split(":", 1)[1]))
            elif item == "refresh":
                self.ctrl.refresh_quotas()
            elif item == "quit":
                self.ctrl.quit()

    def on_finished(self, *_):
        if not self.closing:  # l'indicateur s'est arrêté tout seul : on bascule sur l'icône Qt
            self.ctrl.tray_failed()

    def hide(self):
        self.closing = True
        if self.proc.state() != QProcess.NotRunning:
            self.proc.closeWriteChannel()
            if not self.proc.waitForFinished(1500):
                self.proc.kill()


# ---------------------------------------------------------------- icône Qt (tous systèmes)

class Tray(QObject):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.icon = QSystemTrayIcon(ctrl.app_icon)
        self.menu = QMenu()
        self.info_actions = []
        self.last_lines = None
        self.last_icon = None

        self.info_sep = self.menu.addSeparator()
        legend = self.menu.addAction(t("tray.legend"))
        legend.setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction(t("tray.open")).triggered.connect(ctrl.show_main)
        self.menu.addAction(t("tray.settings")).triggered.connect(ctrl.show_settings)
        self.hud_action = self.menu.addAction(t("tray.hud"))
        self.hud_action.setCheckable(True)
        self.hud_action.setChecked(ctrl.config["hud"])
        self.hud_action.toggled.connect(ctrl.set_hud)
        self._choice_menu(t("tray.corner"), [(c, t(f"corner.{c}")) for c in CORNERS],
                          ctrl.config["corner"], ctrl.set_corner)
        self._choice_menu(t("tray.opacity"), [(o, f"{o * 100:.0f} %") for o in OPACITIES],
                          ctrl.config["opacity"], ctrl.set_opacity)
        self.menu.addSeparator()
        self.menu.addAction(t("tray.refresh")).triggered.connect(ctrl.refresh_quotas)
        self.menu.addAction(t("tray.quit")).triggered.connect(ctrl.quit)

        self.icon.setContextMenu(self.menu)
        self.icon.setToolTip(APP_NAME)
        self.icon.activated.connect(self.on_activated)
        self.icon.show()

    def _choice_menu(self, title, choices, current, callback):
        sub = self.menu.addMenu(title)
        group = QActionGroup(sub)
        group.setExclusive(True)
        for value, text in choices:
            action = QAction(text, sub, checkable=True)
            action.setChecked(value == current)
            action.triggered.connect(lambda _checked=False, v=value: callback(v))
            group.addAction(action)
            sub.addAction(action)

    def on_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.ctrl.toggle_main()

    def sync(self, config):
        if self.hud_action.isChecked() != config["hud"]:
            self.hud_action.blockSignals(True)
            self.hud_action.setChecked(config["hud"])
            self.hud_action.blockSignals(False)

    def update(self, groups):
        lines = info_lines(groups)
        if lines != self.last_lines:
            for action in self.info_actions:
                self.menu.removeAction(action)
            self.info_actions = []
            for text in lines or [t("tray.no_data")]:
                action = QAction(text, self.menu)
                action.triggered.connect(self.ctrl.show_main)
                self.menu.insertAction(self.info_sep, action)
                self.info_actions.append(action)
            self.last_lines = lines
        text = label_text(groups)
        self.icon.setToolTip(f"{APP_NAME}\n{text}" if text else APP_NAME)
        q = next((g for g in groups if g.get("wins")), None)
        verdicts = tuple(b.pace.verdict for _w, b in q["wins"][:2]) if q else ()
        if verdicts != self.last_icon:
            self.icon.setIcon(QIcon(tray_pixmap(verdicts)) if verdicts else self.ctrl.app_icon)
            self.last_icon = verdicts

    def hide(self):
        self.icon.hide()
