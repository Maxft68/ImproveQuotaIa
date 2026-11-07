"""Éléments graphiques : barre de quota (avec repère du temps écoulé) et pastille de conseil."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..pace import COLORS, DOWN, NONE, OK, OUT, SLOW, UP

GREEN, AMBER, RED, GREY = QColor("#4dc778"), QColor("#f5a82e"), QColor("#eb5454"), QColor("#737882")


def level_color(frac: float, warn: float, crit: float) -> QColor:
    return RED if frac >= crit else AMBER if frac >= warn else GREEN


class BarWidget(QWidget):
    """Barre arrondie = part consommée ; trait blanc = part du temps écoulée dans la fenêtre."""

    def __init__(self, min_width: int = 130, parent=None):
        super().__init__(parent)
        self.frac, self.color, self.elapsed = 0.0, GREY, None
        self.setMinimumWidth(min_width)
        self.setFixedHeight(16)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, frac: Optional[float], color: QColor, elapsed: Optional[float] = None) -> None:
        frac = 0.0 if frac is None else max(0.0, min(1.0, frac))
        if (frac, color.name(), elapsed) != (self.frac, self.color.name(), self.elapsed):
            self.frac, self.color, self.elapsed = frac, color, elapsed
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        h = 10.0
        x, y, w = 2.0, (self.height() - h) / 2, self.width() - 4.0
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)
        if self.frac > 0:
            p.setBrush(self.color)
            p.drawRoundedRect(QRectF(x, y, max(h, w * self.frac), h), h / 2, h / 2)
        if self.elapsed is not None:
            tx = x + w * max(0.0, min(1.0, self.elapsed))
            p.setBrush(QColor(0, 0, 0, 140))
            p.drawRect(QRectF(tx - 2, y - 3, 4, h + 6))
            p.setBrush(QColor(255, 255, 255, 242))
            p.drawRect(QRectF(tx - 1, y - 3, 2, h + 6))


def draw_verdict(p: QPainter, cx: float, cy: float, r: float, verdict: Optional[str]) -> None:
    """Pastille colorée avec flèche : ↑ monte, → garde, ↓ baisse, ⇊ ralentis, ✕ épuisé."""
    if verdict is None:
        return
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(COLORS[verdict]))
    p.drawEllipse(QPointF(cx, cy), r, r)
    pen = QPen(QColor(255, 255, 255), max(1.2, r * 0.28))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    k = r * 0.5
    path = QPainterPath()

    def poly(*points):
        path.moveTo(cx + points[0][0], cy + points[0][1])
        for dx, dy in points[1:]:
            path.lineTo(cx + dx, cy + dy)

    if verdict == UP:
        poly((0, k), (0, -k))
        poly((-k * 0.75, -k * 0.2), (0, -k), (k * 0.75, -k * 0.2))
    elif verdict == DOWN:
        poly((0, -k), (0, k))
        poly((-k * 0.75, k * 0.2), (0, k), (k * 0.75, k * 0.2))
    elif verdict == OK:
        poly((-k, 0), (k, 0))
        poly((k * 0.2, -k * 0.75), (k, 0), (k * 0.2, k * 0.75))
    elif verdict == SLOW:
        for dy in (-k * 0.55, k * 0.25):
            poly((-k * 0.8, dy - k * 0.3), (0, dy + k * 0.35), (k * 0.8, dy - k * 0.3))
    elif verdict == OUT:
        poly((-k * 0.7, -k * 0.7), (k * 0.7, k * 0.7))
        poly((k * 0.7, -k * 0.7), (-k * 0.7, k * 0.7))
    else:
        poly((-k * 0.6, 0), (k * 0.6, 0))
    p.drawPath(path)


class VerdictIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.verdict = None
        self.setFixedSize(QSize(16, 16))

    def set_verdict(self, verdict: Optional[str]) -> None:
        if verdict != self.verdict:
            self.verdict = verdict
            self.update()

    def paintEvent(self, _event):
        draw_verdict(QPainter(self), 8, 8, 7.5, self.verdict)


def tray_pixmap(verdicts, size: int = 64) -> QPixmap:
    """Icône de la zone de notification : une pastille par fenêtre (ex. 5 h et 7 j)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    verdicts = [v for v in verdicts if v] or [NONE]
    if len(verdicts) == 1:
        draw_verdict(p, size / 2, size / 2, size * 0.45, verdicts[0])
    else:
        r = size * 0.24
        draw_verdict(p, size * 0.26, size / 2, r, verdicts[0])
        draw_verdict(p, size * 0.74, size / 2, r, verdicts[1])
    p.end()
    return pm
