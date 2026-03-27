import sys
import os
import subprocess
from pathlib import Path

def ensure_dependencies():
    """Verifica e instala dependencias si faltan (ej. redis)."""
    try:
        import celery
        import redis
    except ImportError:
        print("Instalando dependencias necesarias para Worker. Esto puede tardar un momento...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

ensure_dependencies()

# Añadir src/ al PYTHONPATH en runtime
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
os.environ["PYTHONPATH"] = str(_SRC_DIR)

if __name__ == "__main__":
    from celery.bin.celery import main
    print("Iniciando Worker de Celery...")

    # Simula ejecutar `celery -A api.worker.celery_app worker --loglevel=info`
    # Si estás en Windows nativo (sin WSL), puedes necesitar agregar el flag `--pool=solo`
    # si encuentras problemas con el multiprocessing de Windows.
    sys.argv = ["celery", "-A", "api.worker.celery_app", "worker", "--loglevel=info"]

    if os.name == 'nt':
        # Fallback para Windows en caso de que multiprocessing falle por falta de fork()
        sys.argv.append("--pool=solo")

    main()
