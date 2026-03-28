import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.session import get_db
from db.models import User, Project, ProjectAttachment, AuditLog
from api.services.security import get_current_user

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.get("/{project_id}/attachments")
async def list_attachments(
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

    atts_result = await db.execute(select(ProjectAttachment).filter(ProjectAttachment.project_id == project_id))
    return atts_result.scalars().all()

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

    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if project.status in ["PROCESSING", "GENERATING_HTML", "GENERATING_PDF"]:
        raise HTTPException(status_code=400, detail="No puedes adjuntar archivos mientras se genera el reporte.")

    project_dir = UPLOAD_DIR / str(project_id) / "attachments"
    project_dir.mkdir(parents=True, exist_ok=True)

    file_path = project_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_att = ProjectAttachment(
        project_id=project.id,
        filename=file.filename,
        file_path=str(file_path),
        category=category
    )

    db.add(new_att)

    audit = AuditLog(
        user_id=current_user.id,
        action="UPLOAD_ATTACHMENT",
        details=f"Uploaded PDF {file.filename} as {category} for project {project_id}"
    )
    db.add(audit)

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
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project or (not current_user.is_admin and project.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    att_result = await db.execute(select(ProjectAttachment).filter(ProjectAttachment.id == att_id, ProjectAttachment.project_id == project_id))
    att = att_result.scalars().first()

    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Borrar físico
    if os.path.exists(att.file_path):
        os.remove(att.file_path)

    await db.delete(att)
    await db.commit()
    return None
