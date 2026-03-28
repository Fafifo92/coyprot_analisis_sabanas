from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from db.session import get_db
from db.models import User, Project, AuditLog
from api.schemas.api_models import ProjectCreate, ProjectResponse
from api.services.security import get_current_user

router = APIRouter()

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Project)
    if not current_user.is_admin:
        query = query.filter(Project.owner_id == current_user.id)

    result = await db.execute(query.order_by(Project.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validar que el usuario tenga tokens suficientes (si no es admin)
    if not current_user.is_admin:
        if current_user.tokens_balance <= 0:
            raise HTTPException(
                status_code=403,
                detail="No tienes suficientes tokens para crear un nuevo proyecto/caso."
            )
        # Descontar token
        current_user.tokens_balance -= 1
    # Si es Admin, no se descuenta ningún token y puede crear infinitos proyectos.

    # Crear proyecto
    new_project = Project(
        owner_id=current_user.id,
        case_number=project_in.case_number,
        target_phone=project_in.target_phone,
        target_name=project_in.target_name,
        period=project_in.period,
        status="PENDING_FILES"
    )

    db.add(new_project)

    audit = AuditLog(
        user_id=current_user.id,
        action="CREATE_PROJECT",
        details=f"Created project case {project_in.case_number} targeting phone {project_in.target_phone}"
    )
    db.add(audit)

    await db.commit()
    await db.refresh(new_project)

    return new_project

from api.schemas.api_models import ProjectUserUpdate
import pandas as pd
from pathlib import Path

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_in: ProjectUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this project")

    # Solo bloquear la edición si el proyecto está activamente procesándose
    # Permitir edición si el proyecto está pendiente o ya fue generado y se quiere volver a procesar con los nuevos cambios (anti-abuso rule support)
    if project.status in ["PROCESSING", "QUEUED", "QUEUED_PDF", "GENERATING_HTML", "GENERATING_PDF"]:
        raise HTTPException(status_code=400, detail="Cannot edit project while it is actively processing.")

    update_data = project_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    audit = AuditLog(
        user_id=current_user.id,
        action="UPDATE_PROJECT",
        details=f"Updated project case {project.case_number} (ID: {project_id})"
    )
    db.add(audit)

    await db.commit()
    await db.refresh(project)
    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")

    # Borrar la carpeta física en /output/ si existe
    import shutil
    from pathlib import Path
    output_dir = Path("output") / str(project.id)
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)

    upload_dir = Path("uploads") / str(project.id)
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    await db.delete(project)

    audit = AuditLog(
        user_id=current_user.id,
        action="DELETE_PROJECT",
        details=f"Deleted project case {project.case_number} (ID: {project_id})"
    )
    db.add(audit)

    await db.commit()
    return None

@router.get("/{project_id}/numbers")
async def get_project_numbers(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lee rápidamente los archivos Excel mapeados y devuelve una lista de números de teléfono únicos
    presentes (originadores y receptores) para que el usuario pueda asignarles nombres/alias en el frontend.
    """
    result = await db.execute(select(Project).options(selectinload(Project.files)).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    from services.data_processing_service import DataProcessingService
    data_svc = DataProcessingService()

    unique_numbers = set()
    for file in project.files:
        if file.status == "MAPPED" and file.sheet_configs:
            sheets, _ = data_svc.load_sheets_raw(Path(file.file_path))
            if sheets:
                try:
                    df = data_svc.process_sheets(sheets, file.sheet_configs)
                    if "originador" in df.columns:
                        unique_numbers.update(df["originador"].dropna().astype(str).unique())
                    if "receptor" in df.columns:
                        unique_numbers.update(df["receptor"].dropna().astype(str).unique())
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error procesando hojas para sacar números en {file.filename}: {e}")

    # Remover campos en blanco y ordenar
    unique_numbers.discard("")
    unique_numbers.discard("nan")
    unique_numbers.discard("None")

    return {"numbers": sorted(list(unique_numbers))}

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this project")

    return project
