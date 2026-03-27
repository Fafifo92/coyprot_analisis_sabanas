from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import pandas as pd
from pathlib import Path
import logging

from db.session import get_db
from db.models import User, Project, ProjectFile, AuditLog
from api.services.security import get_current_user
from api.worker.tasks import analyze_project_task, generate_pdf_task

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{project_id}/analyze")
async def start_analysis(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.files))
        .filter(Project.id == project_id)
    )
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not any(f.status == "MAPPED" for f in project.files):
        raise HTTPException(status_code=400, detail="No hay archivos mapeados para analizar en este proyecto.")

    project.status = "QUEUED"

    audit = AuditLog(
        user_id=current_user.id,
        action="START_ANALYSIS",
        details=f"Started analysis for project {project_id}"
    )
    db.add(audit)
    await db.commit()

    # Encolar la tarea en Celery Worker
    analyze_project_task.delay(project_id)

    return {"message": "Análisis encolado correctamente. Consulta el estado del proyecto más tarde."}

@router.post("/{project_id}/generate-pdf")
async def generate_pdf(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if project.status not in ["COMPLETED_HTML", "COMPLETED_ALL", "FAILED"]:
        raise HTTPException(status_code=400, detail="Debe finalizar el análisis HTML primero para generar el PDF.")

    project.status = "QUEUED_PDF"

    audit = AuditLog(
        user_id=current_user.id,
        action="REQUEST_PDF",
        details=f"Requested PDF generation for project {project_id}"
    )
    db.add(audit)
    await db.commit()

    generate_pdf_task.delay(project_id)

    return {"message": "Generación de PDF pesada encolada correctamente."}
