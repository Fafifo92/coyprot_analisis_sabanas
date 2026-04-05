from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from db.session import get_db
from db.models import User
from api.schemas.api_models import ProjectCreate, ProjectResponse, ProjectUserUpdate
from api.services.security import get_current_user
from api.repositories.project_repository import ProjectRepository
from api.repositories.audit_repository import AuditRepository
from api.repositories.user_repository import UserRepository
import pandas as pd
from pathlib import Path

router = APIRouter()

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    return await project_repo.get_by_owner(current_user.id, skip=skip, limit=limit)

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_repo = UserRepository(db)

    # Validar que el usuario tenga tokens suficientes (si no es admin)
    # Por defecto, crear un proyecto cuesta 1 token (reporte HTML gratis)
    required_tokens = 1

    if not current_user.is_admin:
        if current_user.tokens_balance < required_tokens:
            raise HTTPException(
                status_code=403,
                detail=f"Necesitas al menos {required_tokens} token(s) para crear un nuevo caso de investigación."
            )
        # Descontar token
        await user_repo.update(current_user, {"tokens_balance": current_user.tokens_balance - required_tokens})

    project_repo = ProjectRepository(db)
    new_project = await project_repo.create(current_user.id, project_in.model_dump())

    # We update the status for compatibility with old routing
    await project_repo.update(new_project, {"status": "PENDING_FILES"})

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "CREATE_PROJECT", f"Created project case {project_in.case_number} targeting phone {project_in.target_phone}")

    await db.commit()
    await db.refresh(new_project)

    return new_project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_in: ProjectUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id_with_files(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this project")

    # Bloquear la edición de metadata básica si el proyecto está procesando
    # OJO: Permitimos la edición del pdf_draft siempre y cuando no esté generando el PDF en ese exacto milisegundo
    if project.status in ["PROCESSING", "QUEUED", "QUEUED_PDF", "GENERATING_HTML", "GENERATING_PDF"]:
        # Only block if they are trying to change core data, allow pdf_draft updates
        update_data = project_in.model_dump(exclude_unset=True)
        if any(key in update_data for key in ["case_number", "target_phone", "target_name", "aliases", "column_mapping"]):
            raise HTTPException(status_code=400, detail="No se pueden editar los detalles centrales del caso mientras se procesa. Espere a que termine.")

    update_data = project_in.model_dump(exclude_unset=True)
    project = await project_repo.update(project, update_data)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "UPDATE_PROJECT", f"Updated project case {project.case_number} (ID: {project_id})")

    await db.commit()
    await db.refresh(project)
    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)

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

    await project_repo.delete(project)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "DELETE_PROJECT", f"Deleted project case {project.case_number} (ID: {project_id})")

    await db.commit()
    return None

@router.get("/{project_id}/numbers")
async def get_project_numbers(
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
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this project")

    # Si el proyecto ya está mapeado, calcular las fechas min/max para el PDF builder
    min_date = None
    max_date = None
    if project.status not in ["PENDING_FILES", "PENDING_MAPPING"]:
        from services.data_processing_service import DataProcessingService
        data_svc = DataProcessingService()
        import pandas as pd
        for file in project.files:
            if file.status == "MAPPED" and file.sheet_configs:
                sheets, _ = data_svc.load_sheets_raw(Path(file.file_path))
                if sheets:
                    try:
                        df = data_svc.process_sheets(sheets, file.sheet_configs)
                        if "fecha_hora" in df.columns:
                            valid_dates = pd.to_datetime(df["fecha_hora"], errors="coerce").dropna()
                            if not valid_dates.empty:
                                file_min = valid_dates.min()
                                file_max = valid_dates.max()
                                if min_date is None or file_min < min_date:
                                    min_date = file_min
                                if max_date is None or file_max > max_date:
                                    max_date = file_max
                    except Exception:
                        pass

    response = project.to_dict()
    if min_date and max_date:
        response["min_date"] = min_date.strftime("%Y-%m-%dT%H:%M")
        response["max_date"] = max_date.strftime("%Y-%m-%dT%H:%M")

    return response
