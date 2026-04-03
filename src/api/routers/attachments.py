import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db.models import User
from api.services.security import get_current_user
from api.repositories.project_repository import ProjectRepository
from api.repositories.audit_repository import AuditRepository

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.get("/{project_id}/attachments")
async def list_attachments(
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

    return await project_repo.get_attachments_for_project(project_id)

@router.post("/{project_id}/attachments")
async def upload_attachment(
    project_id: int,
    category: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF.")

    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if project.status in ["PROCESSING", "GENERATING_HTML", "GENERATING_PDF"]:
        raise HTTPException(status_code=400, detail="No puedes adjuntar archivos mientras se genera el reporte.")

    safe_filename = Path(file.filename).name
    project_dir = UPLOAD_DIR / str(project_id) / "attachments"
    project_dir.mkdir(parents=True, exist_ok=True)

    file_path = project_dir / safe_filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_att = await project_repo.create_attachment(project.id, safe_filename, str(file_path), category)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "UPLOAD_ATTACHMENT", f"Uploaded PDF {safe_filename} as {category} for project {project_id}")

    await db.commit()
    await db.refresh(new_att)

    return new_att

@router.delete("/{project_id}/attachments/{att_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    project_id: int,
    att_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)

    if not project or (not current_user.is_admin and project.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    att = await project_repo.get_attachment_by_id(att_id, project_id)

    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Borrar físico
    if os.path.exists(att.file_path):
        os.remove(att.file_path)

    await project_repo.delete_attachment(att)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "DELETE_ATTACHMENT", f"Deleted PDF {att.filename} from project {project_id}")

    await db.commit()
    return None
