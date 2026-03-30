import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
import json
from db.models import User
from api.schemas.file_models import FileUploadResponse, ProjectFileMapRequest, SheetMappingConfig
from api.services.security import get_current_user
from api.repositories.project_repository import ProjectRepository
from api.repositories.audit_repository import AuditRepository
from services.data_processing_service import DataProcessingService

router = APIRouter()
data_service = DataProcessingService()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.get("/{project_id}/files", response_model=list[FileUploadResponse])
async def list_project_files(
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

    return await project_repo.get_files_for_project(project_id)

@router.post("/{project_id}/files/upload", response_model=FileUploadResponse)
async def upload_file(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Guardar archivo temporalmente
    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(exist_ok=True)

    safe_filename = Path(file.filename).name
    file_path = project_dir / safe_filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Leer hojas y columnas sin GUI
    try:
        # load_sheets_raw devuelve (dict_of_dataframes, error_msg)
        sheets, error = data_service.load_sheets_raw(file_path)
        if error or not sheets:
            raise Exception(error or "El archivo está vacío o no es un formato válido.")

        detected_sheets = {name: list(df.columns) for name, df in sheets.items()}
    except Exception as exc:
        # Borrar el archivo si falla
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error al procesar el archivo: {str(exc)}")

    # Guardar en base de datos
    new_file = await project_repo.create_file(project.id, safe_filename, str(file_path), detected_sheets)

    await project_repo.update(project, {"status": "PENDING_MAPPING"})

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "UPLOAD_FILE", f"Uploaded {file.filename} to project {project_id}")

    await db.commit()
    await db.refresh(new_file)

    # Devolver DTO adaptado
    return FileUploadResponse(
        id=new_file.id,
        filename=new_file.filename,
        detected_sheets=new_file.detected_sheets,
        status=new_file.status
    )

@router.post("/{project_id}/files/{file_id}/map")
async def save_file_mapping(
    project_id: int,
    file_id: int,
    request: ProjectFileMapRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Verificar archivo
    project_file = await project_repo.get_file_by_id(file_id, project_id)

    if not project_file:
        raise HTTPException(status_code=404, detail="File not found in this project")

    # Guardar la configuración de mapeo
    configs_list = [config.model_dump() for config in request.configs]
    project_file.sheet_configs = configs_list
    project_file.status = "MAPPED"

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "MAP_FILE", f"Mapped file {project_file.filename} in project {project_id}")

    await db.commit()

    return {"message": "Mapeo guardado exitosamente. Estado persistido."}
