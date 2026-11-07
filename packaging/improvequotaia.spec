# PyInstaller : `pyinstaller packaging/improvequotaia.spec` depuis la racine du dépôt.
# Produit dist/ImproveQuotaIa/ (Linux, Windows) ou dist/ImproveQuotaIa.app (macOS), avec deux exécutables :
#   ImproveQuotaIa            l'application (sans console)
#   improvequotaia-statusline la status line de Claude Code (console, démarrage rapide, sans Qt)
import sys

block_cipher = None
excluded = ["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
            "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts"]

# Textes de licence (GPLv3 + composants tiers embarqués, dont PySide6/Qt en LGPLv3) livrés avec les exécutables.
licenses = [("../LICENSE", "."), ("../THIRD_PARTY_LICENSES", ".")]
# Indicateur avec texte (Linux) : exécuté par le Python du système, donc copié tel quel.
indicator = [("../src/improvequotaia/linux_indicator.py", "improvequotaia")]

app_a = Analysis(["entry.py"], pathex=["../src"], datas=licenses + indicator, excludes=excluded,
                 cipher=block_cipher)
sl_a = Analysis(["statusline_entry.py"], pathex=["../src"], excludes=excluded + ["PySide6"], cipher=block_cipher)

app_pyz = PYZ(app_a.pure, cipher=block_cipher)
sl_pyz = PYZ(sl_a.pure, cipher=block_cipher)

app_exe = EXE(app_pyz, app_a.scripts, [], exclude_binaries=True, name="ImproveQuotaIa", console=False)
sl_exe = EXE(sl_pyz, sl_a.scripts, [], exclude_binaries=True, name="improvequotaia-statusline", console=True)

coll = COLLECT(app_exe, app_a.binaries, app_a.datas, sl_exe, sl_a.binaries, sl_a.datas, name="ImproveQuotaIa")

if sys.platform == "darwin":
    app = BUNDLE(coll, name="ImproveQuotaIa.app", bundle_identifier="io.github.maxft68.improvequotaia",
                 info_plist={"LSUIElement": True, "NSHighResolutionCapable": True})
