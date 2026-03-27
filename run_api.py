import sys
import os
import subprocess
from pathlib import Path

def ensure_dependencies():
    """Verifica e instala dependencias si faltan (ej. aiosqlite)."""
    try:
        import uvicorn
        import aiosqlite
        import fastapi
    except ImportError:
        print("Instalando dependencias necesarias. Esto puede tardar un momento...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

ensure_dependencies()

# Importar uvicorn de forma segura tras garantizar su instalación
import uvicorn

# Añadir src/ al PYTHONPATH en runtime para que no haya errores
# de "ModuleNotFoundError: No module named 'api'" en Windows.
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
os.environ["PYTHONPATH"] = str(_SRC_DIR)

if __name__ == "__main__":
    # Levanta FastAPI en el puerto 8000
    print("Iniciando Servidor Coyprot SaaS en http://127.0.0.1:8000")
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
