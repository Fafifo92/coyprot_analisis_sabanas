from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from db.session import get_db
from db.models import User
from api.services.security import get_current_user
from api.worker.tasks import analyze_project_task, generate_pdf_task
from config.api_settings import get_api_settings
from api.repositories.project_repository import ProjectRepository
from api.repositories.audit_repository import AuditRepository
from api.repositories.user_repository import UserRepository

api_settings = get_api_settings()

router = APIRouter()
logger = logging.getLogger(__name__)

import threading

@router.post("/{project_id}/analyze")
async def start_analysis(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id_with_files(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not any(f.status == "MAPPED" for f in project.files):
        raise HTTPException(status_code=400, detail="No hay archivos mapeados para analizar en este proyecto.")

    await project_repo.update(project, {"status": "QUEUED"})

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "START_ANALYSIS", f"Started analysis for project {project_id}")
    await db.commit()

    if api_settings.CELERY_ENABLED:
        try:
            analyze_project_task.delay(project_id)
            return {"message": "Análisis encolado en Celery correctamente."}
        except Exception as e:
            logger.error(f"Error conectando a Celery/Redis ({e}). Haciendo fallback a Threads locales.")

    # Fallback Local / Windows sin Redis (Evita el WinError 10061 de Kombu)
    def fallback_analyze():
        try:
            analyze_project_task(project_id)
        except Exception as fall_err:
            logger.exception(f"Error crítico en Thread local para proyecto {project_id}: {fall_err}")
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from db.models import Project

            sync_engine = create_engine(api_settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite"))
            SyncSessionLocal = sessionmaker(bind=sync_engine)
            with SyncSessionLocal() as sync_db:
                p = sync_db.query(Project).filter(Project.id == project_id).first()
                if p:
                    p.status = "FAILED"
                    p.error_message = f"Error fatal del sistema local: {str(fall_err)}"
                    sync_db.commit()

    # Ejecuta el mismo worker pero localmente en un hilo
    threading.Thread(target=fallback_analyze, daemon=True).start()

    return {"message": "Análisis iniciado en segundo plano (Modo Local)."}

@router.post("/{project_id}/generate-pdf")
async def generate_pdf(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    user_repo = UserRepository(db)
    project = await project_repo.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if project.status not in ["COMPLETED_HTML", "COMPLETED_ALL", "FAILED"]:
        raise HTTPException(status_code=400, detail="Debe finalizar el análisis HTML primero para generar el PDF.")

    # Deduct 2 tokens for PDF Generation
    required_tokens = 2
    if not current_user.is_admin:
        if current_user.tokens_balance < required_tokens:
            raise HTTPException(
                status_code=403,
                detail=f"Necesitas al menos {required_tokens} token(s) para exportar el informe PDF personalizado."
            )
        await user_repo.update(current_user, {"tokens_balance": current_user.tokens_balance - required_tokens})

    await project_repo.update(project, {"status": "QUEUED_PDF"})

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "REQUEST_PDF", f"Requested PDF generation for project {project_id}")
    await db.commit()

    if api_settings.CELERY_ENABLED:
        try:
            generate_pdf_task.delay(project_id)
            return {"message": "Generación de PDF encolada en Celery."}
        except Exception as e:
            logger.error(f"Error conectando a Celery/Redis ({e}). Fallback local.")

    def fallback_pdf():
        try:
            generate_pdf_task(project_id)
        except Exception as fall_err:
            logger.exception(f"Error crítico en Thread local PDF para proyecto {project_id}: {fall_err}")
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from db.models import Project

            sync_engine = create_engine(api_settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite"))
            SyncSessionLocal = sessionmaker(bind=sync_engine)
            with SyncSessionLocal() as sync_db:
                p = sync_db.query(Project).filter(Project.id == project_id).first()
                if p:
                    p.status = "FAILED"
                    p.error_message = f"Error fatal generando PDF: {str(fall_err)}"
                    sync_db.commit()

    threading.Thread(target=fallback_pdf, daemon=True).start()

    return {"message": "Generación de PDF iniciada en segundo plano (Modo Local)."}
