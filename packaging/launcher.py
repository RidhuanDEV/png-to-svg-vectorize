"""Entry point of the frozen desktop app (PyInstaller)."""
import multiprocessing
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()          # worker processes re-enter here and must stop at this line
    from pngsvg_app.desktop import main
    sys.exit(main())
