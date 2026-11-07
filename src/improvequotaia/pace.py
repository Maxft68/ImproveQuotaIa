"""Conseil de rythme : comparer la part de tokens consommée (la barre) à la part du temps écoulée
dans la fenêtre de quota (le trait blanc)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

UP, OK, DOWN, SLOW, OUT, NONE = "up", "ok", "down", "slow", "out", "none"

COLORS = {UP: "#4dc778", OK: "#5c9efa", DOWN: "#f5a82e", SLOW: "#eb5454", OUT: "#eb5454", NONE: "#737882"}
ARROWS = {UP: "↑", OK: "→", DOWN: "↓", SLOW: "⇊", OUT: "✕", NONE: "·"}
SEVERITY = {UP: 0, OK: 1, DOWN: 2, SLOW: 3, OUT: 4}

# Seuils, en points de pourcentage (écart trait − barre)
UP_GAP = 0.05       # barre au moins 5 pts derrière le trait → monte
OK_GAP = -0.03      # jusqu'à 3 pts devant → garde
DOWN_GAP = -0.10    # 3 à 10 pts devant → baisse ; au-delà → ralentis
END_WINDOW = 0.15   # fin de fenêtre : moins de 15 % du temps restant…
END_RATIO = 1.5     # …et au moins 1,5× plus de tokens que de temps → monte (ne pas gaspiller)


@dataclass
class Pace:
    verdict: str
    left: float                 # part de tokens restante (0..1)
    time_left: Optional[float]  # part de temps restante (0..1), None si inconnue

    @property
    def used(self) -> float:
        return 1.0 - self.left

    @property
    def elapsed(self) -> Optional[float]:
        return None if self.time_left is None else 1.0 - self.time_left

    @property
    def gap(self) -> Optional[float]:
        """> 0 : barre derrière le trait (marge) ; < 0 : barre devant le trait (trop rapide)."""
        return None if self.time_left is None else self.left - self.time_left


def compute_pace(frac: Optional[float], reset_at: Optional[datetime], window_s: Optional[int],
                 now: datetime, disabled: bool = False) -> Optional[Pace]:
    if disabled or frac is None:
        return None
    left = max(0.0, 1.0 - frac)
    time_left = None
    if reset_at is not None and window_s:
        time_left = min(1.0, max(0.0, (reset_at - now).total_seconds() / window_s))
    if left <= 0.005:
        verdict = OUT
    elif frac <= 0.01:
        verdict = UP  # rien consommé dans cette fenêtre
    elif time_left is None:
        verdict = NONE
    else:
        gap = left - time_left
        end_of_window = time_left < END_WINDOW and left >= END_RATIO * time_left and gap > 0.01
        if gap >= UP_GAP or end_of_window:
            verdict = UP
        elif gap >= OK_GAP:
            verdict = OK
        elif gap >= DOWN_GAP:
            verdict = DOWN
        else:
            verdict = SLOW
    return Pace(verdict, left, time_left)


def worst(verdicts: Iterable[str]) -> str:
    known = [v for v in verdicts if v in SEVERITY]
    return max(known, key=SEVERITY.get) if known else NONE
