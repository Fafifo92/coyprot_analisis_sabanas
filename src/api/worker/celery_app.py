import os
from celery import Celery
from pathlib import Path

# Añadir src al PYTHONPATH para los workers
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
os.environ["PYTHONPATH"] = str(_SRC_DIR)

# En Windows sin Docker, Redis falla dando "WinError 10061".
# Para desarrollo local fácil, usaremos la misma base de datos SQLite como broker.
# En producción, usa REDIS_URL=redis://redis:6379/0 en tu .env o docker-compose.
SQLITE_BROKER = "sqla+sqlite:///./coyprot_api.db"
BROKER_URL = os.getenv("CELERY_BROKER_URL", SQLITE_BROKER)
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "db+sqlite:///./coyprot_api.db")

celery_app = Celery(
    "coyprot_worker",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["api.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
    worker_hijack_root_logger=False, # Mantenemos nuestro logger
    # Aseguramos compatibilidad sqlite para concurrencia
    broker_connection_retry_on_startup=True,
)
