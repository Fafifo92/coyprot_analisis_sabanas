"""
Punto de entrada de la aplicación.

Resuelve el path de importación y lanza la GUI.
Compatible con ejecución directa y con PyInstaller.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Agregar src/ al path para que los imports relativos funcionen
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def main() -> None:
    from ui.app import CallAnalyzerApp
    app = CallAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
