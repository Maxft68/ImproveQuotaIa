"""Fenêtre principale : panneau détaillé complet + légende."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..i18n import t
from ..paths import APP_NAME
from . import theme
from .panel import DetailPanel


class MainWindow(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(ctrl.app_icon)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(12)

        bar = QHBoxLayout()
        self.hud_btn = QPushButton("HUD")
        self.hud_btn.setCheckable(True)
        self.hud_btn.setChecked(ctrl.config["hud"])
        self.hud_btn.setToolTip(t("main.hud_tip"))
        self.hud_btn.toggled.connect(ctrl.set_hud)
        settings = QPushButton(t("main.settings"))
        settings.clicked.connect(ctrl.show_settings)
        refresh = QPushButton(t("main.refresh"))
        refresh.clicked.connect(ctrl.refresh_quotas)
        bar.addWidget(self.hud_btn)
        bar.addStretch(1)
        bar.addWidget(settings)
        bar.addWidget(refresh)
        lay.addLayout(bar)

        self.panel = DetailPanel()
        lay.addWidget(self.panel)
        legend = QLabel(t("main.legend"))
        legend.setWordWrap(True)
        legend.setStyleSheet(theme.DIM)
        lay.addWidget(legend)
        lay.addStretch(1)
        self.resize(580, 10)

    def sync_hud_button(self, on: bool):
        if self.hud_btn.isChecked() != on:
            self.hud_btn.blockSignals(True)
            self.hud_btn.setChecked(on)
            self.hud_btn.blockSignals(False)

    def closeEvent(self, event):
        if self.ctrl.tray is not None:  # l'application reste dans la zone de notification
            event.ignore()
            self.hide()
        else:
            self.ctrl.quit()
