"""Assistant de premier lancement : on coche les outils utilisés, et c'est fini."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QVBoxLayout

from .. import claude_integration
from ..i18n import provider_label, t
from ..paths import APP_NAME
from ..shortcuts import DESKTOP, MENU
from . import theme


def note(text: str, indent: bool = True) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(theme.DIM + (" margin-left: 22px;" if indent else ""))
    return label


class WelcomeDialog(QDialog):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(ctrl.app_icon)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        title = QLabel(t("wizard.title", app=APP_NAME))
        f = QFont(title.font())
        f.setPointSizeF(f.pointSizeF() * 1.4)
        f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)
        lay.addWidget(note(t("wizard.intro"), indent=False))

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        self.provider_boxes = {}
        for r, p in enumerate(ctrl.providers):
            box = QCheckBox(provider_label(p) + (f"  ({t('tools.experimental')})" if p.experimental else ""))
            box.setChecked(ctrl.detected[p.id])
            found = QLabel("✓ " + t("tools.detected") if ctrl.detected[p.id] else t("tools.not_found"))
            found.setStyleSheet(theme.DIM)
            grid.addWidget(box, r, 0)
            grid.addWidget(found, r, 1)
            self.provider_boxes[p.id] = box
        lay.addLayout(grid)

        options = QLabel(t("wizard.options"))
        options.setStyleSheet(theme.SECTION + " margin-top: 8px;")
        lay.addWidget(options)
        self.system_box = QCheckBox(t("wizard.system"))
        self.hud_box = QCheckBox(t("wizard.hud"))
        self.autostart_box = QCheckBox(t("general.autostart"))
        self.menu_box = QCheckBox(t("wizard.menu_shortcut"))
        self.desktop_box = QCheckBox(t("wizard.desktop_shortcut"))
        for box in (self.system_box, self.hud_box, self.autostart_box):
            box.setChecked(True)
            lay.addWidget(box)
        self.menu_box.setChecked(True)
        self.desktop_box.setChecked(True)
        lay.addWidget(self.menu_box)
        lay.addWidget(self.desktop_box)
        lay.addWidget(note(t("wizard.relaunch_note")))

        # Barre d'état de Claude Code : la case reflète l'état réel (cochée = branchée)
        self.sl_state = claude_integration.status()
        self.sl_box = QCheckBox(t("wizard.statusline"))
        self.sl_note = note("")
        lay.addWidget(self.sl_box)
        lay.addWidget(self.sl_note)
        claude_box = self.provider_boxes["claude"]
        self.sl_box.setChecked(self.sl_state == "ours" or (ctrl.detected["claude"] and self.sl_state in ("none", "other")))
        claude_box.toggled.connect(self._refresh_statusline)
        self._refresh_statusline()

        lay.addWidget(note(t("wizard.privacy"), indent=False))
        buttons = QDialogButtonBox()
        buttons.addButton(t("wizard.finish"), QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)
        self.setMinimumWidth(520)

    def _refresh_statusline(self, *_):
        claude_on = self.provider_boxes["claude"].isChecked()
        usable = claude_on and self.sl_state != "error"
        self.sl_box.setEnabled(usable)
        self.sl_box.setToolTip("" if usable else t("wizard.statusline_disabled"))
        if self.sl_state == "error":
            text = t("sl.error")
        elif not claude_on:
            text = t("wizard.statusline_disabled")
        elif self.sl_state == "ours":
            text = t("wizard.statusline_ours")
        else:
            text = t("sl.explain") + ("\n" + t("sl.other") if self.sl_state == "other" else "")
        self.sl_note.setText(text)

    def choices(self) -> dict:
        claude_on = self.provider_boxes["claude"].isChecked()
        want_sl = claude_on and self.sl_box.isChecked()
        return {
            "providers": {pid: box.isChecked() for pid, box in self.provider_boxes.items()},
            "system": self.system_box.isChecked(),
            "hud": self.hud_box.isChecked(),
            "autostart": self.autostart_box.isChecked(),
            MENU: self.menu_box.isChecked(),
            DESKTOP: self.desktop_box.isChecked(),
            # True = brancher, False = débrancher, None = ne rien changer
            "statusline": (True if want_sl and self.sl_state != "ours"
                           else False if not want_sl and self.sl_state == "ours" and claude_on
                           else None),
        }
