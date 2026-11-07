"""HUD : le panneau détaillé, translucide, toujours au premier plan et traversé par la souris.
Il s'efface quand la souris s'approche et se cache quand une application est en plein écran."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..paths import APP_NAME
from ..platform_utils import fullscreen_active, x11_make_sticky
from .panel import DetailPanel

NEAR_ALPHA = 0.06
MARGIN = 12


class Hud(QWidget):
    def __init__(self, ctrl):
        flags = (Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                 | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.ctrl = ctrl
        self.setWindowTitle(f"{APP_NAME} HUD")
        for attr in (Qt.WA_TranslucentBackground, Qt.WA_ShowWithoutActivating, Qt.WA_MacAlwaysShowToolWindow,
                     Qt.WA_X11DoNotAcceptFocus):
            self.setAttribute(attr, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        self.panel = DetailPanel(compact=True)
        font = self.panel.font()
        font.setPointSizeF(max(7.5, font.pointSizeF() * 0.85))
        self.panel.setFont(font)
        lay.addWidget(self.panel)

        self.alpha = ctrl.config["opacity"]
        self.setWindowOpacity(self.alpha)
        self.suppressed = False

        self.pointer_timer = QTimer(self)
        self.pointer_timer.timeout.connect(self.poll_pointer)
        self.pointer_timer.start(200)
        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.timeout.connect(self.check_fullscreen)
        self.fullscreen_timer.start(2000)

    # -- dessin du fond arrondi (le contenu est dessiné par les widgets enfants)
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 32), 1))
        p.setBrush(QColor(14, 16, 21, 235))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

    # -- position / visibilité
    def place(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        size = self.sizeHint().expandedTo(self.minimumSizeHint())
        corner = self.ctrl.config["corner"]
        x = geo.left() + MARGIN if "left" in corner else geo.right() - size.width() - MARGIN + 1
        y = geo.top() + MARGIN if "top" in corner else geo.bottom() - size.height() - MARGIN + 1
        self.resize(size)
        self.move(x, y)

    def apply_visibility(self):
        want = self.ctrl.config["hud"] and self.ctrl.config["first_run_done"] and not self.suppressed
        if want and not self.isVisible():
            x11_make_sticky(int(self.winId()))  # tous les bureaux virtuels (X11)
            self.place()
            self.show()
        elif not want and self.isVisible():
            self.hide()

    def check_fullscreen(self):
        if self.ctrl.config["hud"]:
            self.suppressed = fullscreen_active()
            self.apply_visibility()

    def poll_pointer(self):
        if not self.isVisible():
            return
        near = self.frameGeometry().adjusted(-24, -24, 24, 24).contains(QCursor.pos())
        target = NEAR_ALPHA if near else self.ctrl.config["opacity"]
        if abs(self.alpha - target) > 0.005:
            alpha = self.alpha + (target - self.alpha) * 0.35
            self.alpha = target if abs(alpha - target) < 0.02 else alpha
            self.setWindowOpacity(self.alpha)

    # -- données
    def update_sections(self, specs):
        self.apply_visibility()
        if self.isVisible() and self.panel.show_sections(specs):
            self.place()  # structure changée : nouvelle taille, on recolle au coin choisi
