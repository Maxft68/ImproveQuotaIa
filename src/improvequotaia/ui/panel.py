"""Panneau détaillé (fenêtre principale et HUD) : une seule grille pour que les colonnes
restent alignées d'une section à l'autre. Reconstruit seulement quand sa structure change."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QWidget

from ..i18n import t
from ..pace import COLORS, NONE
from ..providers.base import Bucket
from ..utils import fmt_abs, fmt_left
from . import theme
from .widgets import BarWidget, VerdictIcon, level_color


@dataclass
class RowSpec:
    key: str
    name: str
    sub: str = ""
    bucket: Optional[Bucket] = None
    level: Optional[tuple] = None  # (frac, détail, infobulle, seuil orange, seuil rouge) pour le système


@dataclass
class SectionSpec:
    id: str
    title: str
    status: str = ""
    error: bool = False
    tooltip: Optional[str] = None
    rows: List[RowSpec] = field(default_factory=list)


def window_label(win: str) -> str:
    key = f"win.{win}"
    label = t(key)
    return win if label == key else label


def bucket_sub(b: Bucket) -> str:
    """Libellé de la fenêtre, précédé d'une précision éventuelle (« Premium · mois »)."""
    label = window_label(b.win)
    return f"{b.win_label} · {label.lower()}" if b.win_label else label


def pace_detail(b: Bucket) -> Optional[str]:
    pace = b.pace
    if not pace or pace.time_left is None:
        return None
    gap = (pace.elapsed - pace.used) * 100
    where = t("pace.behind") if gap >= 0 else t("pace.ahead")
    return t("pace.detail", used=f"{pace.used * 100:.0f}", elapsed=f"{pace.elapsed * 100:.0f}",
             gap=f"{abs(gap):.0f}", where=where)


class Row:
    def __init__(self, grid: QGridLayout, r: int, compact: bool, font: QFont):
        bold = QFont(font)
        bold.setBold(True)
        self.name = QLabel()
        self.name.setFont(bold)
        self.sub = QLabel()
        self.sub.setStyleSheet(theme.DIM)
        self.bar = BarWidget(90 if compact else 130)
        self.pct = QLabel("—")
        self.pct.setFont(bold)
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pct.setMinimumWidth(self.pct.fontMetrics().horizontalAdvance("100 %") + 2)
        self.extra = QLabel()
        self.extra.setStyleSheet(theme.DIM)
        for label in (self.sub, self.extra):
            label.setFont(font)
        self.verdict = QWidget()
        box = QHBoxLayout(self.verdict)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        self.vicon = VerdictIcon()
        self.vtext = QLabel()
        self.vtext.setFont(bold)
        box.addWidget(self.vicon)
        box.addWidget(self.vtext)
        box.addStretch(1)
        self.widgets = (self.name, self.sub, self.bar, self.pct, self.extra, self.verdict)
        for col, w in enumerate(self.widgets):
            grid.addWidget(w, r, col)

    def _tooltip(self, text: Optional[str]) -> None:
        text = text or ""
        if getattr(self, "_tip", None) != text:
            self._tip = text
            for w in self.widgets:
                w.setToolTip(text)

    def show_level(self, name, frac, extra, tooltip, warn, crit):
        self.name.setText(name)
        disabled = frac is None
        self.bar.set(frac, QColor("#737882") if disabled else level_color(frac, warn, crit))
        self.pct.setText("—" if disabled else f"{frac * 100:.0f} %")
        self.extra.setText(extra or "")
        self.vicon.set_verdict(None)
        self.vtext.setText("")
        self._tooltip(tooltip)

    def show_bucket(self, name: str, sub: str, b: Bucket):
        self.name.setText(name)
        self.sub.setText(sub)
        pace = b.pace
        verdict = pace.verdict if pace else NONE
        self.bar.set(b.frac, QColor(COLORS[verdict]), pace.elapsed if pace else None)
        self.pct.setText("—" if b.disabled or b.frac is None else f"{b.frac * 100:.0f} %")
        if b.note:
            extra = b.note
        elif b.reset_at:
            extra = t("reset.in", left=fmt_left(b.reset_at))
        else:
            extra = ""
        self.extra.setText(extra)
        self.vicon.set_verdict(verdict if pace else None)
        if pace and verdict != NONE:
            self.vtext.setText(t(f"verdict.{verdict}"))
            style = f"color: {COLORS[verdict]};"
            if self.vtext.styleSheet() != style:
                self.vtext.setStyleSheet(style)
        else:
            self.vtext.setText("")
        tips = [b.tooltip]
        if b.reset_at:
            tips.append(t("tip.reset", when=fmt_abs(b.reset_at)))
        if pace_detail(b):
            tips.append(pace_detail(b))
        if pace and verdict != NONE:
            tips.append("→ " + t(f"advice.{verdict}"))
        self._tooltip("\n".join(x for x in tips if x))


class DetailPanel(QWidget):
    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self.compact = compact
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8 if compact else 10)
        self.grid.setVerticalSpacing(2 if compact else 6)
        self.grid.setColumnStretch(2, 1)
        self.signature = None
        self.rows = {}
        self.headers = {}
        self.items = []

    def _clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rows, self.headers = {}, {}

    def _rebuild(self, specs: List[SectionSpec]):
        self._clear()
        r = 0
        if not specs:
            empty = QLabel(t("panel.empty"))
            empty.setFont(self.font())
            empty.setStyleSheet(theme.DIM)
            self.grid.addWidget(empty, 0, 0, 1, 6)
            return
        for i, s in enumerate(specs):
            if i:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setStyleSheet("color: rgba(255, 255, 255, 35);")
                self.grid.addWidget(line, r, 0, 1, 6)
                r += 1
            title, status = QLabel(), QLabel()
            title.setStyleSheet(theme.SECTION)
            small = QFont(self.font())
            small.setPointSizeF(max(7.0, small.pointSizeF() - 1.5))
            title.setFont(small)
            status.setFont(self.font())
            status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.grid.addWidget(title, r, 0, 1, 3)
            self.grid.addWidget(status, r, 3, 1, 3)
            self.headers[s.id] = (title, status)
            r += 1
            for spec in s.rows:
                self.rows[(s.id, spec.key)] = Row(self.grid, r, self.compact, self.font())
                r += 1

    def show_sections(self, specs: List[SectionSpec]) -> bool:
        """Met à jour l'affichage ; renvoie True si la structure (donc la taille) a changé."""
        signature = tuple((s.id, tuple(r.key for r in s.rows)) for s in specs)
        changed = signature != self.signature
        if changed:
            self._rebuild(specs)
            self.signature = signature
        for s in specs:
            title, status = self.headers[s.id]
            title.setText(s.title)
            status.setText(("⚠ " if s.error else "") + s.status)
            style = theme.ERROR if s.error else theme.DIM
            if status.styleSheet() != style:
                status.setStyleSheet(style)
            if status.toolTip() != (s.tooltip or ""):
                status.setToolTip(s.tooltip or "")
            last_name = None
            for spec in s.rows:
                row = self.rows[(s.id, spec.key)]
                name = spec.name if spec.name != last_name else ""
                last_name = spec.name
                if spec.bucket is not None:
                    row.show_bucket(name, spec.sub, spec.bucket)
                else:
                    frac, extra, tip, warn, crit = spec.level
                    row.show_level(name, frac, extra, tip, warn, crit)
        return changed
