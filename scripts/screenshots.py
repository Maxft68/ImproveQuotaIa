#!/usr/bin/env python3
"""Génère les captures de démonstration du README avec des données FICTIVES (docs/*.png).

Ce sont les vrais composants de l'application (HUD, fenêtre, texte de la barre du haut), dessinés hors
écran puis posés sur un poste de travail fictif (fond d'écran, fenêtre neutre, dock).

Usage : python scripts/screenshots.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(["improvequotaia"])

from improvequotaia import i18n  # noqa: E402
from improvequotaia.i18n import t  # noqa: E402
from improvequotaia.pace import OK, UP, compute_pace  # noqa: E402
from improvequotaia.providers.base import FIVE_H, WEEK, Bucket  # noqa: E402
from improvequotaia.ui.hud import Hud  # noqa: E402
from improvequotaia.ui.main_window import MainWindow  # noqa: E402
from improvequotaia.ui.panel import RowSpec, SectionSpec, bucket_sub  # noqa: E402
from improvequotaia.ui.theme import apply_dark  # noqa: E402
from improvequotaia.ui.tray import label_text, main_verdict  # noqa: E402
from improvequotaia.ui.widgets import tray_pixmap  # noqa: E402

apply_dark(app)
DPR = float(os.environ["QT_SCALE_FACTOR"])
NOW = datetime.now(timezone.utc)
DOCS = ROOT / "docs"

# ---------------------------------------------------------------- données fictives

def bucket(key, gid, label, win, used, elapsed, window_s, **kw):
    reset = NOW + timedelta(seconds=(1 - elapsed) * window_s) if elapsed is not None else None
    b = Bucket(key=key, group=gid, group_label=label, win=win, frac=used, reset_at=reset, window_s=window_s, **kw)
    b.pace = compute_pace(b.frac, b.reset_at, b.window_s, NOW, b.disabled)
    return b


def demo():
    claude = [bucket("c5", "claude-code", "Claude Code", "5h", 0.64, 0.58, FIVE_H),
              bucket("c7", "claude-code", "Claude Code", "7d", 0.34, 0.60, WEEK)]
    gemini = [bucket("g5", "ag-gemini", "Gemini", "5h", 0.12, 0.35, FIVE_H),
              bucket("g7", "ag-gemini", "Gemini", "7d", 0.22, 0.24, WEEK)]
    third = [bucket("p5", "ag-3p", "Claude / GPT", "5h", 0.48, 0.47, FIVE_H),
             bucket("p7", "ag-3p", "Claude / GPT", "7d", 0.81, 0.55, WEEK)]
    argon = [bucket("a5", "ag-argon", "Argon", "5h", None, None, FIVE_H, disabled=True, note=t("note.no_5h")),
             bucket("a7", "ag-argon", "Argon", "7d", 0.09, 0.30, WEEK)]
    codex = [bucket("x5", "codex", "Codex", "5h", 0.30, 0.62, FIVE_H),
             bucket("x7", "codex", "Codex", "7d", 0.71, 0.69, WEEK)]

    def rows(buckets):
        return [RowSpec(b.key, b.group_label, bucket_sub(b), bucket=b) for b in buckets]

    def ago(n, source=None):
        return t("status.updated", ago=t("ago.s", n=n)) + (f" · {source}" if source else "")

    system = SectionSpec("system", t("section.system"), t("status.every_second"), rows=[
        RowSpec("cpu", "CPU", level=(0.23, "54 °C", None, 0.6, 0.85)),
        RowSpec("ram", "RAM", level=(0.61, f"9.5 / 15.6 {t('unit.gb')}", None, 0.75, 0.9)),
        RowSpec("gpu", "GPU", level=(0.41, "61 °C · 95 W", None, 0.6, 0.85)),
        RowSpec("vram", "VRAM", level=(0.38, f"3.0 / 8.0 {t('unit.gb')}", None, 0.75, 0.9)),
    ])
    specs = [
        system,
        SectionSpec("claude", "CLAUDE · Max · Opus 5.5 (high)", ago(2, "Claude Code"), rows=rows(claude)),
        SectionSpec("antigravity", "ANTIGRAVITY", ago(4), rows=rows(gemini + third + argon)),
        SectionSpec("codex", "CODEX", ago(31, "Codex"), rows=rows(codex)),
    ]
    tray_groups = [{"label": label, "wins": [(b.win, b) for b in group if b.pace]}
                   for label, group in (("Claude Code", claude), ("Gemini", gemini), ("Claude / GPT", third),
                                        ("Argon", argon), ("Codex", codex))]
    return specs, tray_groups


def fake_ctrl():
    return SimpleNamespace(config={"hud": True, "opacity": 0.92, "corner": "top-right", "first_run_done": True},
                           app_icon=QIcon(tray_pixmap((UP, OK))), tray=None, set_hud=lambda *_: None,
                           show_settings=lambda *_: None, refresh_quotas=lambda *_: None, quit=lambda *_: None)


# ---------------------------------------------------------------- dessin

def canvas(w, h):
    img = QImage(int(w * DPR), int(h * DPR), QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(DPR)
    img.fill(Qt.transparent)
    return img


def rounded(p, rect, radius, color, pen=None):
    p.setPen(pen or Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(rect, radius, radius)


def draw_wallpaper(p, W, H):
    grad = QLinearGradient(0, 0, W, H)
    grad.setColorAt(0.0, QColor(36, 20, 70))
    grad.setColorAt(0.55, QColor(108, 38, 92))
    grad.setColorAt(1.0, QColor(214, 86, 52))
    p.fillRect(QRectF(0, 0, W, H), grad)
    p.setPen(Qt.NoPen)
    for cx, cy, r, alpha in ((W * 0.18, H * 0.82, 380, 18), (W * 0.62, H * 0.28, 300, 12), (W * 0.9, H * 0.9, 260, 16)):
        p.setBrush(QColor(255, 255, 255, alpha))
        p.drawEllipse(QPointF(cx, cy), r, r)


def draw_generic_window(p, rect):
    """Fenêtre d'application neutre (blocs gris), pour figurer un poste de travail sans détail inutile."""
    for i in range(10, 0, -1):
        rounded(p, rect.adjusted(-i, -i + 8, i, i + 8), 12 + i, QColor(0, 0, 0, 9))
    rounded(p, rect, 12, QColor(246, 246, 248))
    bar = QRectF(rect.x(), rect.y(), rect.width(), 40)
    rounded(p, bar.adjusted(0, 0, 0, 12), 12, QColor(232, 232, 236))
    p.fillRect(QRectF(rect.x(), rect.y() + 40, rect.width(), 12), QColor(246, 246, 248))
    for i in range(3):
        rounded(p, QRectF(rect.right() - 30 - i * 24, rect.y() + 14, 12, 12), 6, QColor(196, 196, 204))
    rounded(p, QRectF(rect.x() + 90, rect.y() + 10, rect.width() - 220, 20), 10, QColor(250, 250, 252))
    side = QRectF(rect.x() + 18, rect.y() + 62, 150, rect.height() - 80)
    for i in range(7):
        rounded(p, QRectF(side.x(), side.y() + i * 34, 120 - (i % 3) * 22, 14), 7, QColor(214, 214, 222))
    content_x = rect.x() + 196
    width = rect.right() - content_x - 24
    rounded(p, QRectF(content_x, rect.y() + 62, width * 0.55, 22), 8, QColor(200, 200, 210))
    for i in range(4):
        rounded(p, QRectF(content_x, rect.y() + 104 + i * 24, width * (0.95 - 0.12 * (i % 2)), 12), 6,
                QColor(224, 224, 230))
    card_w = (width - 24) / 3
    for i in range(3):
        rounded(p, QRectF(content_x + i * (card_w + 12), rect.y() + 220, card_w, rect.height() - 244), 10,
                QColor(234, 234, 240))


def draw_dock(p, W, H):
    colors = ((240, 120, 60), (70, 140, 230), (60, 180, 120), (230, 190, 60), (150, 100, 220), (90, 90, 100))
    size, gap = 46, 14
    total = len(colors) * size + (len(colors) - 1) * gap + 28
    dock = QRectF((W - total) / 2, H - size - 26, total, size + 16)
    rounded(p, dock, 18, QColor(20, 20, 24, 170))
    for i, rgb in enumerate(colors):
        icon = QRectF(dock.x() + 14 + i * (size + gap), dock.y() + 8, size, size)
        rounded(p, icon, 12, QColor(*rgb))
        rounded(p, icon.adjusted(14, 14, -14, -14), 6, QColor(255, 255, 255, 200))


def draw_top_bar(p, W, tray_groups):
    p.fillRect(QRectF(0, 0, W, 32), QColor(13, 13, 15))
    p.setFont(QFont(app.font().family(), 10.5))
    p.setPen(QColor(230, 230, 235))
    p.drawText(QRectF(0, 0, W, 32), Qt.AlignCenter, "18:42")
    p.drawText(QPointF(18, 21), t("demo.activities"))
    text = label_text(tray_groups)
    fm = p.fontMetrics()
    right = W - 64
    tx = right - fm.horizontalAdvance(text)
    icon = tray_pixmap([main_verdict(tray_groups)], 64)
    p.drawPixmap(QRectF(tx - 28, 6, 20, 20), icon, QRectF(0, 0, 64, 64))
    p.drawText(QPointF(tx, 21), text)
    p.setBrush(QColor(230, 230, 235))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(W - 40, 16), 4, 4)  # icônes système (stylisées)
    p.drawRoundedRect(QRectF(W - 26, 11, 10, 10), 2, 2)


def hud_scene(specs, tray_groups, path):
    W, H = 1440, 810
    img = canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    draw_wallpaper(p, W, H)
    draw_generic_window(p, QRectF(70, 90, 760, 500))
    draw_dock(p, W, H)
    draw_top_bar(p, W, tray_groups)
    # HUD (vrai composant), translucide, en haut à droite sous la barre
    hud = Hud(fake_ctrl())
    hud.pointer_timer.stop()
    hud.fullscreen_timer.stop()
    hud.panel.show_sections(specs)
    hud.adjustSize()
    hud.show()
    app.processEvents()
    pm = hud.grab()
    size = pm.deviceIndependentSize()
    p.setOpacity(0.94)
    p.drawPixmap(QPointF(W - size.width() - 16, 44), pm)
    p.end()
    hud.close()
    img.save(str(path))


def window_scene(specs, path):
    win = MainWindow(fake_ctrl())
    win.panel.show_sections(specs)
    win.resize(640, 10)
    win.adjustSize()
    win.show()
    app.processEvents()
    pm = win.grab()
    size = pm.deviceIndependentSize()
    pad, bar = 48, 38
    W, H = size.width() + pad * 2, size.height() + bar + pad * 2
    img = canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, W, H)
    grad.setColorAt(0, QColor(58, 44, 92))
    grad.setColorAt(1, QColor(20, 72, 96))
    p.fillRect(QRectF(0, 0, W, H), grad)
    frame = QRectF(pad, pad, size.width(), size.height() + bar)
    for i in range(12, 0, -1):  # ombre douce
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 10))
        p.drawRoundedRect(frame.adjusted(-i, -i + 6, i, i + 6), 14 + i, 14 + i)
    p.setBrush(QColor(32, 33, 36))
    p.drawRoundedRect(frame, 12, 12)
    p.setBrush(QColor(42, 43, 47))
    p.drawRoundedRect(QRectF(frame.x(), frame.y(), frame.width(), bar + 12), 12, 12)
    p.fillRect(QRectF(frame.x(), frame.y() + bar, frame.width(), 12), QColor(32, 33, 36))
    p.setPen(QColor(235, 235, 240))
    f = QFont(app.font().family(), 10.5)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(frame.x(), frame.y(), frame.width(), bar), Qt.AlignCenter, "ImproveQuotaIa")
    for i, color in enumerate(((95, 97, 104), (95, 97, 104), (95, 97, 104))):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*color))
        p.drawEllipse(QPointF(frame.right() - 22 - i * 26, frame.y() + bar / 2), 7, 7)
    p.drawPixmap(QPointF(pad, pad + bar), pm)
    p.end()
    win.close()
    img.save(str(path))


def main():
    DOCS.mkdir(exist_ok=True)
    for lang in ("en", "fr"):
        i18n.set_language(lang)
        specs, tray_groups = demo()
        hud_scene(specs, tray_groups, DOCS / f"hud-{lang}.png")
        window_scene(specs, DOCS / f"window-{lang}.png")
        print(f"docs/hud-{lang}.png, docs/window-{lang}.png")


if __name__ == "__main__":
    main()
