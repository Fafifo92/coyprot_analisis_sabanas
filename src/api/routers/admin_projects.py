from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel

from db.session import get_db
from db.models import User, Project, AuditLog
from api.schemas.api_models import ProjectResponse
from api.services.security import get_current_admin

router = APIRouter()

class ProjectAdminUpdate(BaseModel):
    case_number: Optional[str] = None
    target_phone: Optional[str] = None
    target_name: Optional[str] = None
    period: Optional[str] = None
    status: Optional[str] = None # Para forzar reinicio (ej: "PENDING_MAPPING")

@router.get("/projects", response_model=List[ProjectResponse])
async def list_all_projects(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Lista todos los proyectos en el sistema para el panel de SuperAdmin.
    """
    result = await db.execute(select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project_admin(
    project_id: int,
    project_in: ProjectAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Permite al Admin editar datos fijos de un caso o forzar un reinicio de estado.
    """
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_in.model_dump(exclude_unset=True)

    # Si se cambia el estado a un estado inicial, limpiamos el mensaje de error anterior
    if "status" in update_data and update_data["status"] in ["PENDING_FILES", "PENDING_MAPPING"]:
        project.error_message = None
        project.result_html_path = None
        project.result_pdf_path = None

    for key, value in update_data.items():
        setattr(project, key, value)

    audit = AuditLog(user_id=admin.id, action="ADMIN_UPDATE_PROJECT", details=f"Admin updated project {project_id}")
    db.add(audit)

    await db.commit()
    await db.refresh(project)
    return project

@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_admin(
    project_id: int,
    refund_token: bool = False,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Permite al Admin eliminar el caso y, opcionalmente, devolver el token gastado.
    """
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if refund_token:
        # Devolver token al dueño (si no es admin)
        owner_result = await db.execute(select(User).filter(User.id == project.owner_id))
        owner = owner_result.scalars().first()
        if owner and not owner.is_admin:
            owner.tokens_balance += 1

    # Eliminar carpetas
    import shutil
    from pathlib import Path
    for p in [Path("output") / str(project.id), Path("uploads") / str(project.id)]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    await db.delete(project)

    audit = AuditLog(
        user_id=admin.id,
        action="ADMIN_DELETE_PROJECT",
        details=f"Admin deleted project {project_id}. Refunded token: {refund_token}"
    )
    db.add(audit)
    await db.commit()
    return None
