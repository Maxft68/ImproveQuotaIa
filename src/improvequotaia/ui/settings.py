"""Réglages : ce qu'affiche chaque vue, outils suivis, options générales."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget,
                               QVBoxLayout, QWidget)

from .. import __version__, claude_integration
from ..about import AUTHOR, AUTHOR_URL, DONATE_URL, ISSUES_URL, REPO_URL
from ..paths import APP_NAME
from ..config import DISPLAYS, is_shown
import sys

from ..i18n import provider_label, t
from ..platform_utils import autostart_enabled
from ..shortcuts import DESKTOP, MENU, has_shortcut
from . import theme
from .tray import CORNERS, OPACITIES

SYS_ITEMS = (("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU"), ("vram", "VRAM"))


def bold(label: QLabel) -> QLabel:
    f = QFont(label.font())
    f.setBold(True)
    label.setFont(f)
    return label


class SettingsDialog(QDialog):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setWindowTitle(t("settings.title"))
        self.setWindowIcon(ctrl.app_icon)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._display_tab(), t("settings.tab_display"))
        tabs.addTab(self._tools_tab(), t("settings.tab_tools"))
        tabs.addTab(self._general_tab(), t("settings.tab_general"))
        tabs.addTab(self._about_tab(), t("settings.tab_about"))
        lay.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        lay.addWidget(buttons)

    # -- onglet « Affichage » : tableau de cases (élément × vue)
    def _display_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        grid = QGridLayout()
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(6)
        for col, display in enumerate(DISPLAYS, 1):
            head = bold(QLabel(t(f"display.{display}")))
            head.setAlignment(Qt.AlignCenter)
            grid.addWidget(head, 0, col)
        sections = (
            (t("section.system"), SYS_ITEMS, True),
            (t("settings.quotas"), self.ctrl.all_groups(), True),
            (t("settings.windows"), (("5h", t("win.5h_long")), ("7d", t("win.7d_long")),
                                     ("1d", t("win.1d_long")), ("1mo", t("win.1mo_long"))), True),
        )
        r = 1
        for title, items, in_tray in sections:
            label = QLabel(title.upper())
            label.setStyleSheet(theme.SECTION + " margin-top: 6px;")
            grid.addWidget(label, r, 0, 1, 4)
            r += 1
            for key, text in items:
                grid.addWidget(QLabel(text), r, 0)
                for col, display in enumerate(DISPLAYS, 1):
                    if display == "tray" and not in_tray:
                        dash = QLabel("—")
                        dash.setStyleSheet(theme.DIM)
                        dash.setAlignment(Qt.AlignCenter)
                        grid.addWidget(dash, r, col)
                        continue
                    box = QCheckBox()
                    box.setChecked(is_shown(self.ctrl.config, display, key))
                    box.toggled.connect(lambda on, d=display, k=key: self.ctrl.set_item_shown(d, k, on))
                    cell = QWidget()
                    h = QHBoxLayout(cell)
                    h.setContentsMargins(0, 0, 0, 0)
                    h.addWidget(box, alignment=Qt.AlignCenter)
                    grid.addWidget(cell, r, col)
                r += 1
        lay.addLayout(grid)
        note = QLabel(t("settings.display_note"))
        note.setWordWrap(True)
        note.setStyleSheet(theme.DIM)
        lay.addWidget(note)
        lay.addStretch(1)
        return page

    # -- onglet « Outils »
    def _tools_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        form = QGridLayout()
        for r, p in enumerate(self.ctrl.providers):
            box = QCheckBox(provider_label(p) + (f"  ({t('tools.experimental')})" if p.experimental else ""))
            box.setChecked(self.ctrl.enabled(p.id))
            box.toggled.connect(lambda on, pid=p.id: self.ctrl.set_provider_enabled(pid, on))
            found = QLabel(t("tools.detected") if self.ctrl.detected[p.id] else t("tools.not_found"))
            found.setStyleSheet(theme.DIM)
            form.addWidget(box, r, 0)
            form.addWidget(found, r, 1)
        lay.addLayout(form)

        group = QGroupBox(t("sl.title"))
        g = QVBoxLayout(group)
        explain = QLabel(t("sl.explain"))
        explain.setWordWrap(True)
        explain.setStyleSheet(theme.DIM)
        g.addWidget(explain)
        row = QHBoxLayout()
        self.sl_status = QLabel()
        self.sl_button = QPushButton()
        self.sl_button.clicked.connect(self._toggle_statusline)
        row.addWidget(self.sl_status, 1)
        row.addWidget(self.sl_button)
        g.addLayout(row)
        lay.addWidget(group)
        lay.addStretch(1)
        self._refresh_statusline()
        return page

    def _refresh_statusline(self):
        state = claude_integration.status()
        self.sl_status.setText(t(f"sl.{state}"))
        self.sl_button.setText(t("sl.uninstall") if state == "ours" else t("sl.install"))
        self.sl_button.setEnabled(state != "error")

    def _toggle_statusline(self):
        try:
            if claude_integration.status() == "ours":
                claude_integration.uninstall()
            else:
                claude_integration.install()
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, t("settings.title"), t("sl.failed", err=e))
        self._refresh_statusline()

    # -- onglet « À propos » : auteur, liens, soutien
    def _about_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)
        title = QLabel(f"{APP_NAME} {__version__}")
        f = QFont(title.font())
        f.setPointSizeF(f.pointSizeF() * 1.3)
        f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)
        by = QLabel(t("about.by", author=f'<a href="{AUTHOR_URL}">{AUTHOR}</a>'))
        links = QLabel(f'<a href="{REPO_URL}">{t("about.source")}</a> &nbsp;·&nbsp; '
                       f'<a href="{ISSUES_URL}">{t("about.issues")}</a>')
        for label in (by, links):
            label.setTextFormat(Qt.RichText)
            label.setOpenExternalLinks(True)
            lay.addWidget(label)
        license_ = QLabel(t("about.license"))
        license_.setStyleSheet(theme.DIM)
        lay.addWidget(license_)

        support = QLabel(t("about.support"))
        support.setStyleSheet(theme.SECTION + " margin-top: 12px;")
        lay.addWidget(support)
        explain = QLabel(t("about.donate_note"))
        explain.setWordWrap(True)
        explain.setStyleSheet(theme.DIM)
        lay.addWidget(explain)
        donate = QPushButton("☕  " + t("about.donate"))
        donate.setToolTip(DONATE_URL)
        donate.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DONATE_URL)))
        row = QHBoxLayout()
        row.addWidget(donate)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    # -- onglet « Général »
    def _general_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        lang = QComboBox()
        for code, text in (("auto", t("lang.auto")), ("fr", "Français"), ("en", "English")):
            lang.addItem(text, code)
        lang.setCurrentIndex(max(0, lang.findData(self.ctrl.config.get("language", "auto"))))
        lang.currentIndexChanged.connect(lambda _i: self.ctrl.set_language(lang.currentData()))
        form.addRow(t("general.language"), lang)
        note = QLabel(t("general.restart_note"))
        note.setStyleSheet(theme.DIM)
        form.addRow("", note)

        autostart = QCheckBox(t("general.autostart"))
        autostart.setChecked(autostart_enabled())
        autostart.toggled.connect(self.ctrl.set_autostart)
        form.addRow("", autostart)
        for kind, key in ((MENU, "general.menu_shortcut"), (DESKTOP, "general.desktop_shortcut")):
            box = QCheckBox(t(key))
            box.setChecked(has_shortcut(kind))
            box.toggled.connect(lambda on, k=kind: self.ctrl.set_shortcut(k, on))
            form.addRow("", box)
        if sys.platform.startswith("linux"):
            text = QCheckBox(t("general.tray_text"))
            text.setChecked(bool(self.ctrl.config.get("tray_text", True)))
            text.toggled.connect(self.ctrl.set_tray_text)
            form.addRow("", text)
            hint = QLabel(t("general.restart_note"))
            hint.setStyleSheet(theme.DIM)
            form.addRow("", hint)

        corner = QComboBox()
        for c in CORNERS:
            corner.addItem(t(f"corner.{c}"), c)
        corner.setCurrentIndex(max(0, corner.findData(self.ctrl.config["corner"])))
        corner.currentIndexChanged.connect(lambda _i: self.ctrl.set_corner(corner.currentData()))
        form.addRow(t("tray.corner"), corner)

        opacity = QComboBox()
        for o in OPACITIES:
            opacity.addItem(f"{o * 100:.0f} %", o)
        current = min(range(len(OPACITIES)), key=lambda i: abs(OPACITIES[i] - self.ctrl.config["opacity"]))
        opacity.setCurrentIndex(current)
        opacity.currentIndexChanged.connect(lambda _i: self.ctrl.set_opacity(opacity.currentData()))
        form.addRow(t("tray.opacity"), opacity)
        return page
