"""Point d'entrée des exécutables autonomes (PyInstaller)."""
import sys

if "--statusline" in sys.argv[1:]:
    from improvequotaia.statusline import main as statusline_main
    statusline_main()
else:
    from improvequotaia.app import main
    sys.exit(main())
