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

api_settings = get_api_settings()

router = APIRouter()
logger = logging.getLogger(__name__)

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

    # Use Celery. In local environments it uses SQLite as broker.
    analyze_project_task.delay(project_id)
    return {"message": "Análisis encolado correctamente."}

@router.post("/{project_id}/generate-pdf")
async def generate_pdf(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if project.status not in ["COMPLETED_HTML", "COMPLETED_ALL", "FAILED"]:
        raise HTTPException(status_code=400, detail="Debe finalizar el análisis HTML primero para generar el PDF.")

    await project_repo.update(project, {"status": "QUEUED_PDF"})

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "REQUEST_PDF", f"Requested PDF generation for project {project_id}")
    await db.commit()

    generate_pdf_task.delay(project_id)
    return {"message": "Generación de PDF encolada."}
