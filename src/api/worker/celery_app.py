import os
from celery import Celery
from pathlib import Path

# Añadir src al PYTHONPATH para los workers
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
os.environ["PYTHONPATH"] = str(_SRC_DIR)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "coyprot_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["api.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
    worker_hijack_root_logger=False, # Mantenemos nuestro logger
)
