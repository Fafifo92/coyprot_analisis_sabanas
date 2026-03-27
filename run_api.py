import sys
import os
import uvicorn
from pathlib import Path

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
