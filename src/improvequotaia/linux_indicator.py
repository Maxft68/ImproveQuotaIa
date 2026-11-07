#!/usr/bin/env python3
"""Indicateur avec texte pour la barre du haut sous Linux (GNOME/Ubuntu, Budgie, MATE…).

Processus séparé, lancé par ImproveQuotaIa avec le Python du système (celui qui a PyGObject et
AyatanaAppIndicator3) : GTK n'est jamais chargé dans le processus Qt. Qt ne sait pas afficher de
texte à côté d'une icône d'indicateur ; AppIndicator, si.

Protocole (une ligne JSON par message) :
  entrée  : {"label": str, "icon": str, "icon_dir": str, "menu": [entrées]}
  sortie  : {"id": str, "active": bool | null}   (clic dans le menu)
Entrée de menu : {"kind": "item" | "check" | "radio" | "sep" | "submenu" | "label",
                  "id": str, "label": str, "active": bool, "items": [entrées]}
Fin de l'entrée standard (ImproveQuotaIa fermé) → l'indicateur se ferme.
"""
import json
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator  # noqa: E402


def structure(entries):
    return [(e.get("kind"), e.get("id"), structure(e.get("items") or [])) for e in entries or []]


class Indicator:
    def __init__(self):
        self.ind = AppIndicator.Indicator.new("improvequotaia", "", AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_title("ImproveQuotaIa")
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.label = self.icon = self.menu_spec = None
        self.widgets = []      # widgets dans l'ordre de parcours, pour les mises à jour sur place
        self.updating = False
        self.buffer = b""
        GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.on_input)

    # -- entrée
    def on_input(self, fd, condition):
        data = os.read(fd, 65536) if condition & GLib.IO_IN else b""
        if not data:
            Gtk.main_quit()
            return False
        self.buffer += data
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                self.apply(json.loads(line))
            except ValueError:
                pass
        return True

    def apply(self, msg):
        if msg.get("icon_dir"):
            self.ind.set_icon_theme_path(msg["icon_dir"])
        if msg.get("icon") and msg["icon"] != self.icon:
            self.ind.set_icon_full(msg["icon"], "ImproveQuotaIa")
            self.icon = msg["icon"]
        label = msg.get("label") or ""
        if label != self.label:
            self.ind.set_label(label, "")
            self.label = label
        menu = msg.get("menu")
        if menu is not None and menu != self.menu_spec:
            if self.menu_spec is not None and structure(menu) == structure(self.menu_spec):
                self.updating = True
                self._update(menu, iter(self.widgets))
                self.updating = False
            else:
                self.widgets = []
                gtk_menu = self._build(menu)
                gtk_menu.show_all()
                self.ind.set_menu(gtk_menu)
            self.menu_spec = menu

    # -- sortie
    def emit(self, item_id, active=None):
        try:
            sys.stdout.write(json.dumps({"id": item_id, "active": active}) + "\n")
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            Gtk.main_quit()

    # -- construction du menu
    def _build(self, entries):
        menu = Gtk.Menu()
        previous_radio = None
        for e in entries:
            kind = e.get("kind")
            if kind == "sep":
                widget = Gtk.SeparatorMenuItem()
            elif kind == "check":
                widget = Gtk.CheckMenuItem(label=e.get("label", ""))
                widget.set_active(bool(e.get("active")))
                widget.connect("toggled", self._on_toggle, e.get("id"))
            elif kind == "radio":
                widget = Gtk.RadioMenuItem.new_with_label_from_widget(previous_radio, e.get("label", ""))
                widget.set_active(bool(e.get("active")))
                widget.connect("toggled", self._on_radio, e.get("id"))
                previous_radio = widget
            elif kind == "submenu":
                widget = Gtk.MenuItem(label=e.get("label", ""))
                self.widgets.append(widget)
                widget.set_submenu(self._build(e.get("items") or []))
                menu.append(widget)
                continue
            else:
                widget = Gtk.MenuItem(label=e.get("label", ""))
                if kind == "label":
                    widget.set_sensitive(False)
                else:
                    widget.connect("activate", lambda _w, i=e.get("id"): self.emit(i))
            self.widgets.append(widget)
            menu.append(widget)
        return menu

    def _update(self, entries, widgets):
        for e in entries:
            widget = next(widgets)
            if e.get("kind") != "sep":
                widget.set_label(e.get("label", ""))
            if e.get("kind") in ("check", "radio") and widget.get_active() != bool(e.get("active")):
                widget.set_active(bool(e.get("active")))
            if e.get("kind") == "submenu":
                self._update(e.get("items") or [], widgets)

    def _on_toggle(self, widget, item_id):
        if not self.updating:
            self.emit(item_id, widget.get_active())

    def _on_radio(self, widget, item_id):
        if not self.updating and widget.get_active():
            self.emit(item_id, True)


def main():
    Indicator()
    Gtk.main()


if __name__ == "__main__":
    main()
