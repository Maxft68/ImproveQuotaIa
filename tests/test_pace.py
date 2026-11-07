from datetime import datetime, timedelta, timezone

import pytest

from improvequotaia.pace import DOWN, NONE, OK, OUT, SLOW, UP, compute_pace, worst

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
WEEK = 7 * 86400
FIVE_H = 5 * 3600


def pace(used, time_left_frac, window=WEEK):
    return compute_pace(used, NOW + timedelta(seconds=time_left_frac * window), window, NOW)


@pytest.mark.parametrize("used, time_left, expected", [
    (0.80, 0.10, UP),       # 20 % restant pour 10 % du temps : on peut monter
    (0.80, 0.90, SLOW),     # 20 % restant pour 90 % du temps : ralentir
    (0.07, 0.994, DOWN),    # début de semaine, barre 6 pts devant le trait (cas Argon)
    (0.50, 0.50, OK),       # pile dans le rythme
    (0.34, 0.40, UP),       # 34 % consommés pour 60 % écoulés
    (0.95, 0.01, UP),       # fin de fenêtre : ne pas gaspiller
    (0.005, 0.99, UP),      # rien consommé
    (1.0, 0.5, OUT),        # épuisé
])
def test_verdicts(used, time_left, expected):
    assert pace(used, time_left).verdict == expected


def test_unknown_window_and_disabled():
    assert compute_pace(0.5, None, None, NOW).verdict == NONE
    assert compute_pace(0.5, NOW, WEEK, NOW, disabled=True) is None
    assert compute_pace(None, NOW, WEEK, NOW) is None


def test_gap_and_elapsed():
    p = pace(0.64, 0.41, FIVE_H)
    assert p.elapsed == pytest.approx(0.59)
    assert p.gap == pytest.approx(-0.05)


def test_worst():
    assert worst([UP, OK, DOWN]) == DOWN
    assert worst([UP, OUT]) == OUT
    assert worst([]) == NONE
