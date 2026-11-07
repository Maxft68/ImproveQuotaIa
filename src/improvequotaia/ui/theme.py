"""Thème sombre identique sur Linux, macOS et Windows (style Fusion)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DIM = "color: rgba(255, 255, 255, 150);"
SECTION = "color: rgba(255, 255, 255, 165); font-weight: bold;"
ERROR = "color: #eb5757;"


def apply_dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    roles = {
        QPalette.Window: (32, 33, 36), QPalette.WindowText: (232, 232, 232),
        QPalette.Base: (24, 25, 28), QPalette.AlternateBase: (38, 39, 43),
        QPalette.ToolTipBase: (44, 45, 50), QPalette.ToolTipText: (235, 235, 235),
        QPalette.Text: (232, 232, 232), QPalette.Button: (48, 49, 54), QPalette.ButtonText: (232, 232, 232),
        QPalette.BrightText: (255, 90, 90), QPalette.Highlight: (92, 158, 250),
        QPalette.HighlightedText: (255, 255, 255), QPalette.PlaceholderText: (140, 140, 145),
        QPalette.Link: (92, 158, 250),
    }
    for role, rgb in roles.items():
        p.setColor(role, QColor(*rgb))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(120, 120, 125))
    app.setPalette(p)
