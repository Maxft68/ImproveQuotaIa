"""Point d'entrée graphique : instance unique, collecte des quotas en arrière-plan, vues Qt."""
from __future__ import annotations

import dataclasses
import getpass
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

from PySide6.QtCore import QLibraryInfo, QLocale, QObject, Qt, QTimer, QTranslator, Signal
from PySide6.QtGui import QIcon, QImageWriter
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from . import claude_integration
from .config import DISPLAYS, is_shown, load_config, save_config
from .i18n import language as lang_code, set_language, t
from .pace import OK, UP, compute_pace
from .paths import APP_NAME, APP_SLUG, data_dir
from .platform_utils import set_autostart
from .shortcuts import DESKTOP, MENU, set_shortcut
from .providers import ALL_PROVIDERS, ProviderError, ToolMissing
from .system import SystemMonitor
from .ui.hud import Hud
from .ui.main_window import MainWindow
from .ui.panel import RowSpec, SectionSpec, bucket_sub
from .ui.settings import SYS_ITEMS, SettingsDialog
from .ui.theme import apply_dark
from .ui.tray import LinuxTextTray, Tray, indicator_python
from .ui.widgets import tray_pixmap
from .ui.wizard import WelcomeDialog
from .utils import fmt_ago

FILTERABLE_WINDOWS = ("5h", "7d", "1d", "1mo")


class Bridge(QObject):
    """Transmet les résultats des threads de collecte au thread de l'interface."""
    result = Signal(str, object, object)


class Poller(threading.Thread):
    """Collecte les quotas un outil après l'autre (jamais en parallèle) pour éviter les pics CPU."""

    def __init__(self, providers, bridge, is_enabled):
        super().__init__(daemon=True)
        self.providers, self.bridge, self.is_enabled = providers, bridge, is_enabled
        self.wake = threading.Event()
        self._lock = threading.Lock()
        self._last_start: dict[str, float] = {}

    def trigger(self, pid: str | None = None):
        with self._lock:
            if pid is None:
                self._last_start.clear()
            else:
                self._last_start.pop(pid, None)
        self.wake.set()

    def _next_wait(self) -> float:
        now = time.monotonic()
        wait_s = 10.0
        enabled_any = False
        with self._lock:
            for p in self.providers:
                if not self.is_enabled(p.id):
                    continue
                enabled_any = True
                last = self._last_start.get(p.id)
                if last is None:
                    return 0.0
                rem = (last + max(1.0, p.interval)) - now
                if rem <= 0:
                    return 0.0
                wait_s = min(wait_s, rem)
        return wait_s if enabled_any else 2.0

    def run(self):
        while True:
            self.wake.clear()
            for p in self.providers:
                if not self.is_enabled(p.id):
                    continue
                now = time.monotonic()
                with self._lock:
                    last = self._last_start.get(p.id)
                    if last is not None and now < last + max(1.0, p.interval):
                        continue
                    self._last_start[p.id] = now
                try:
                    result, error = p.fetch(), None
                except ProviderError as e:
                    result, error = None, e
                except Exception as e:  # un module défaillant ne doit jamais tuer l'application
                    result, error = None, ProviderError(f"{type(e).__name__}: {e}")
                self.bridge.result.emit(p.id, result, error)

            wait_s = self._next_wait()
            if wait_s > 0:
                self.wake.wait(wait_s)


@dataclasses.dataclass
class State:
    result: object = None
    buckets: list = dataclasses.field(default_factory=list)
    error: str = None
    missing: bool = False


class Controller(QObject):
    def __init__(self, app: QApplication, args, smoke_test: bool = False):
        super().__init__()
        self.app = app
        self.config = load_config()
        language = self.config.get("language", "auto")
        set_language(QLocale.system().name()[:2] if language == "auto" else language)
        # Traductions de Qt lui-même (boutons standard « Fermer », « Annuler »…)
        self.qt_translator = QTranslator(app)
        if self.qt_translator.load(QLocale(lang_code()), "qtbase", "_",
                                   QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(self.qt_translator)
        self.app_icon = QIcon(tray_pixmap((UP, OK)))
        app.setWindowIcon(self.app_icon)

        self.providers = [cls() for cls in ALL_PROVIDERS]
        self.detected = {p.id: p.detect() for p in self.providers}
        self.states = {p.id: State() for p in self.providers}
        self.system = SystemMonitor()
        self.sysm = self.system.read()

        self.bridge = Bridge()
        self.bridge.result.connect(self.on_result, Qt.QueuedConnection)
        self.main = MainWindow(self)
        self.hud = Hud(self)
        self.smoke_test = smoke_test
        self.tray = None
        self.tray_attempts = 0
        self.background_start = "--background" in args
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = self.make_tray()
        self.settings = None
        self.wizard = None

        self.poller = Poller(self.providers, self.bridge, self.enabled)
        self.poller.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.tick()

        if smoke_test:
            return
        if not self.config["first_run_done"]:
            QTimer.singleShot(200, self.show_wizard)
        else:
            self.handle_args(args)

    # -- état
    def enabled(self, pid: str) -> bool:
        value = self.config["providers"].get(pid)
        return self.detected[pid] if value is None else value

    def all_groups(self):
        """Groupes connus + groupes vus dans les données (pour le tableau « Affichage »)."""
        seen, out = set(), []
        for p in self.providers:
            if not self.enabled(p.id):
                continue
            candidates = list(p.groups) + [(b.group, b.group_label) for b in self.states[p.id].buckets]
            for gid, label in candidates:
                if gid not in seen:
                    seen.add(gid)
                    suffix = f" ({p.label})" if p.label not in label else ""
                    out.append((gid, label + suffix))
        return out

    # -- arguments (premier lancement ou relance alors que l'app tourne déjà)
    def handle_args(self, args):
        if "--settings" in args:
            self.show_settings()
        elif "--background" not in args:
            self.show_main()
        elif self.tray is None:
            # À l'ouverture de session, la barre du haut n'est pas toujours prête : on réessaie
            # pendant une minute avant d'ouvrir la fenêtre (seul accès s'il n'y a pas d'icône).
            QTimer.singleShot(3000, self.retry_tray)

    # -- résultats des collecteurs
    def on_result(self, pid, result, error):
        st = self.states[pid]
        st.missing = isinstance(error, ToolMissing)
        if error is not None:
            st.error = str(error)
        else:
            st.error, st.result = None, result
            st.buckets = [dataclasses.replace(b) for b in result.buckets]
        self.tick(read_system=False)

    # -- construction des vues
    def sections(self, display):
        cfg, m, specs = self.config, self.sysm, []
        rows = []
        for item, label in SYS_ITEMS:
            if not is_shown(cfg, display, item):
                continue
            if item == "cpu":
                temp = m.get("cpu_temp")
                rows.append(RowSpec("cpu", label, level=(m["cpu"], f"{temp:.0f} °C" if temp else "",
                                                         t("tip.cores", n=m["cpu_count"]), 0.6, 0.85)))
            elif item == "ram":
                rows.append(RowSpec("ram", label, level=(
                    m["ram"], f"{m['ram_used'] / 2**30:.1f} / {m['ram_total'] / 2**30:.1f} {t('unit.gb')}",
                    None, 0.75, 0.9)))
            elif item == "gpu" and m["gpu_available"]:
                details = " · ".join(x for x in (
                    f"{m['gpu_temp']:.0f} °C" if m.get("gpu_temp") is not None else "",
                    f"{m['gpu_power']:.0f} W" if m.get("gpu_power") is not None else "") if x)
                rows.append(RowSpec("gpu", label, level=(m["gpu"], details if m["gpu"] is not None
                                                         else t("gpu.waiting"), m.get("gpu_name"), 0.6, 0.85)))
            elif item == "vram" and m.get("vram") is not None:
                rows.append(RowSpec("vram", label, level=(
                    m["vram"], f"{m['vram_used'] / 1024:.1f} / {m['vram_total'] / 1024:.1f} {t('unit.gb')}",
                    m.get("gpu_name"), 0.75, 0.9)))
        if rows:
            specs.append(SectionSpec("system", t("section.system"), t("status.every_second"), rows=rows))

        for p in self.providers:
            st = self.states[p.id]
            if not self.enabled(p.id) or st.missing:
                continue
            rows = [RowSpec(b.key, b.group_label, bucket_sub(b), bucket=b) for b in st.buckets
                    if is_shown(cfg, display, b.group, b.win if b.win in FILTERABLE_WINDOWS else None)]
            wanted = any(is_shown(cfg, display, g) for g, _ in p.groups)
            if not rows and (st.buckets or not wanted):
                continue
            res = st.result
            title = p.title + (f" · {res.title_extra}" if res and res.title_extra else "")
            if st.error:
                status, error = st.error, True
            elif res:
                status = t("status.updated", ago=fmt_ago(res.updated_at)) + (f" · {res.source}" if res.source else "")
                error = False
            else:
                status, error = t("status.loading"), False
            specs.append(SectionSpec(p.id, title, status, error, res.note if res else None, rows))
        return specs

    def tray_groups(self):
        groups = []
        for p in self.providers:
            st = self.states[p.id]
            if not self.enabled(p.id) or st.missing:
                continue
            order = []
            for b in st.buckets:
                if b.group not in order:
                    order.append(b.group)
            for gid in order:
                if not is_shown(self.config, "tray", gid):
                    continue
                wins = [(b.win, b) for b in st.buckets if b.group == gid and b.pace and b.win in FILTERABLE_WINDOWS
                        and is_shown(self.config, "tray", gid, b.win)]
                if wins:
                    label = next(b.group_label for b in st.buckets if b.group == gid)
                    groups.append({"id": gid, "label": label, "wins": wins})
        return groups

    def tick(self, read_system: bool = True):
        if read_system:
            self.sysm = self.system.read()
        now = datetime.now(timezone.utc)
        for st in self.states.values():
            for b in st.buckets:
                if b.reset_at and b.reset_at <= now and not b.disabled:
                    b.frac, b.reset_at, b.note = 0.0, None, t("note.reset_done")  # fenêtre écoulée
                b.pace = compute_pace(b.frac, b.reset_at, b.window_s, now, b.disabled)
        if self.main.isVisible():
            self.main.panel.show_sections(self.sections("main"))
        if self.config["hud"] and self.config["first_run_done"]:
            self.hud.update_sections(self.sections("hud"))
        if self.tray:
            self.tray.update(self.tray_groups())

    # -- actions
    def show_main(self):
        self.main.panel.show_sections(self.sections("main"))
        self.main.show()
        self.main.raise_()
        self.main.activateWindow()

    def toggle_main(self):
        if self.main.isVisible() and self.main.isActiveWindow():
            self.main.hide()
        else:
            self.show_main()

    def show_settings(self):
        if self.settings is None or not self.settings.isVisible():
            self.settings = SettingsDialog(self)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def show_wizard(self):
        self.wizard = WelcomeDialog(self)
        self.wizard.accepted.connect(lambda: self.apply_wizard(self.wizard.choices()))
        self.wizard.rejected.connect(self.finish_first_run)
        self.wizard.show()
        self.wizard.raise_()
        self.wizard.activateWindow()

    def apply_wizard(self, choices: dict):
        self.config["providers"] = dict(choices["providers"])
        if not choices["system"]:
            for display in DISPLAYS:
                self.config["hidden"][display] = sorted(set(self.config["hidden"][display])
                                                        | {k for k, _ in SYS_ITEMS})
        self.config["hud"] = choices["hud"]
        try:
            set_autostart(choices["autostart"])
        except OSError as e:
            QMessageBox.warning(None, APP_NAME, t("err.autostart", err=e))
        for kind in (MENU, DESKTOP):
            self.set_shortcut(kind, choices[kind])
        if choices["statusline"] is not None:  # True = brancher, False = débrancher
            try:
                claude_integration.install() if choices["statusline"] else claude_integration.uninstall()
            except (OSError, ValueError) as e:
                QMessageBox.warning(None, APP_NAME, t("sl.failed", err=e))
        self.finish_first_run()

    def finish_first_run(self):
        self.config["first_run_done"] = True
        self.save()
        self.main.sync_hud_button(self.config["hud"])
        if self.tray:
            self.tray.sync(self.config)
        self.refresh_quotas()
        self.tick()
        self.show_main()

    def save(self):
        try:
            save_config(self.config)
        except OSError:
            pass

    def set_item_shown(self, display, item, shown):
        hidden = set(self.config["hidden"][display])
        hidden = hidden - {item} if shown else hidden | {item}
        self.config["hidden"][display] = sorted(hidden)
        self.save()
        self.tick(read_system=False)

    def set_provider_enabled(self, pid, on):
        self.config["providers"][pid] = bool(on)
        self.save()
        self.poller.trigger(pid)
        self.tick(read_system=False)

    def set_hud(self, on):
        on = bool(on)
        if self.config["hud"] != on:
            self.config["hud"] = on
            self.save()
        self.hud.apply_visibility()
        self.main.sync_hud_button(on)
        if self.tray:
            self.tray.sync(self.config)
        self.tick(read_system=False)

    def set_corner(self, corner):
        self.config["corner"] = corner
        self.save()
        self.hud.place()

    def set_opacity(self, value):
        self.config["opacity"] = float(value)
        self.save()

    def set_language(self, code):
        self.config["language"] = code
        self.save()

    def set_autostart(self, on):
        try:
            set_autostart(bool(on))
        except OSError as e:
            QMessageBox.warning(None, APP_NAME, t("err.autostart", err=e))

    def icon_files(self) -> dict:
        """Icône de l'application en PNG (+ ICO / ICNS si Qt sait les écrire), pour les raccourcis."""
        folder = data_dir() / "icons"
        folder.mkdir(parents=True, exist_ok=True)
        pixmap = tray_pixmap((UP, OK), 256)
        formats = {bytes(f).decode().lower() for f in QImageWriter.supportedImageFormats()}
        files = {}
        for ext in ("png", "ico", "icns"):
            if ext in formats:
                path = folder / f"improvequotaia.{ext}"
                if path.exists() or pixmap.save(str(path), ext.upper()):
                    files[ext] = path
        return files

    def set_shortcut(self, kind, on):
        try:
            set_shortcut(kind, bool(on), self.icon_files())
        except OSError as e:
            QMessageBox.warning(None, APP_NAME, t("err.shortcut", err=e))

    def set_tray_text(self, on):
        self.config["tray_text"] = bool(on)
        self.save()

    def make_tray(self):
        if not self.smoke_test:
            python = indicator_python() if self.config.get("tray_text", True) else None
            if python:  # Linux : indicateur avec texte dans la barre du haut
                return LinuxTextTray(self, python)
        return Tray(self)

    def retry_tray(self):
        if self.tray is not None:
            return
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = self.make_tray()
            self.tick(read_system=False)
            return
        self.tray_attempts += 1
        if self.tray_attempts < 20:
            QTimer.singleShot(3000, self.retry_tray)
        elif not self.main.isVisible():
            self.show_main()

    def tray_failed(self):
        """L'indicateur avec texte s'est arrêté : on bascule sur l'icône Qt."""
        self.tray = Tray(self)
        self.tick(read_system=False)

    def refresh_quotas(self):
        self.poller.trigger()

    def quit(self):
        self.system.stop()
        if self.tray:
            self.tray.hide()
        self.app.quit()


def _prepare_platform():
    # Wayland ne permet pas aux applications de rester au premier plan ni de se positionner :
    # on passe par XWayland quand il est disponible.
    if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland" \
            and os.environ.get("DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def main() -> int:
    args = sys.argv[1:]
    if "--statusline" in args:
        from .statusline import main as statusline_main
        statusline_main()
        return 0
    if "--version" in args:
        from . import __version__
        print(f"{APP_NAME} {__version__}")
        return 0
    _prepare_platform()
    QApplication.setApplicationName(APP_NAME)
    QApplication.setDesktopFileName(APP_SLUG)
    app = QApplication([APP_SLUG] + sys.argv[1:])
    app.setQuitOnLastWindowClosed(False)
    apply_dark(app)

    if "--smoke-test" in args:  # intégration continue : tout construire, un passage, quitter
        ctrl = Controller(app, args, smoke_test=True)
        ctrl.show_main()
        ctrl.show_settings()
        WelcomeDialog(ctrl)
        QTimer.singleShot(1500, ctrl.quit)
        return app.exec()

    server_name = f"{APP_SLUG}-{getpass.getuser()}"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(300):  # déjà lancée : on lui transmet la demande et on s'arrête
        socket.write(json.dumps(args).encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)
    ctrl = Controller(app, args)

    def on_connection():
        conn = server.nextPendingConnection()
        if conn is None:
            return
        conn.waitForReadyRead(1000)
        try:
            ctrl.handle_args(json.loads(bytes(conn.readAll()).decode("utf-8") or "[]"))
        except ValueError:
            ctrl.show_main()
        conn.disconnectFromServer()

    server.newConnection.connect(on_connection)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
