"""`python -m improvequotaia` — la status line est traitée avant tout import de Qt (démarrage rapide)."""
import sys

if __name__ == "__main__":
    if "--statusline" in sys.argv[1:]:
        from improvequotaia.statusline import main as statusline_main
        statusline_main()
    else:
        from improvequotaia.app import main
        sys.exit(main())
