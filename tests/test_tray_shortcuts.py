import os
import stat
import sys
from datetime import datetime, timedelta, timezone

import pytest

from improvequotaia import shortcuts
from improvequotaia.i18n import set_language
from improvequotaia.pace import compute_pace
from improvequotaia.providers.base import Bucket
from improvequotaia.ui.tray import info_lines, label_text, main_verdict

NOW = datetime.now(timezone.utc)


def bucket(group_label, win, used, time_left, window_s, win_label=None):
    b = Bucket(key=f"{group_label}/{win}/{win_label}", group=group_label.lower(), group_label=group_label, win=win,
               frac=used, reset_at=NOW + timedelta(seconds=time_left * window_s), window_s=window_s,
               win_label=win_label)
    b.pace = compute_pace(b.frac, b.reset_at, b.window_s, NOW)
    return b


def test_top_bar_label_like_the_old_version():
    set_language("fr")
    groups = [
        {"label": "Claude Code", "wins": [("5h", bucket("Claude Code", "5h", 0.93, 0.25, 18000)),
                                          ("7d", bucket("Claude Code", "7d", 0.38, 0.40, 604800))]},
        {"label": "Claude / GPT", "wins": [("7d", bucket("Claude / GPT", "7d", 1.0, 0.45, 604800))]},
        {"label": "GitHub Copilot", "wins": [("1mo", bucket("GitHub Copilot", "1mo", 0.2, 0.5, 2592000, "Premium"))]},
    ]
    assert label_text(groups) == "Claude 5h⇊ 7j↑ · AG·Claude 7j✕ · Copilot Premium↑"
    assert main_verdict(groups) == "slow"
    assert info_lines(groups)[0].startswith("⇊ Claude Code · 5 h : ralentis")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="raccourcis .desktop : Linux")
def test_linux_shortcuts(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(shortcuts, "desktop_dir", lambda: tmp_path / "Bureau")
    shortcuts.set_shortcut(shortcuts.MENU, True, {"png": tmp_path / "icon.png"})
    shortcuts.set_shortcut(shortcuts.DESKTOP, True)
    menu = tmp_path / "data" / "applications" / "improvequotaia.desktop"
    desk = tmp_path / "Bureau" / "improvequotaia.desktop"
    assert shortcuts.has_shortcut(shortcuts.MENU) and shortcuts.has_shortcut(shortcuts.DESKTOP)
    text = menu.read_text()
    assert "Exec=" in text and "-m improvequotaia" in text and f"Icon={tmp_path / 'icon.png'}" in text
    assert "--settings" in text and os.stat(desk).st_mode & stat.S_IXUSR
    shortcuts.set_shortcut(shortcuts.DESKTOP, False)
    assert not desk.exists() and menu.exists()
