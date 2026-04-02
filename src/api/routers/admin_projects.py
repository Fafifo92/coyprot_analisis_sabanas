from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from db.session import get_db
from db.models import User
from api.schemas.api_models import ProjectResponse
from api.services.security import get_current_admin
from api.repositories.project_repository import ProjectRepository
from api.repositories.audit_repository import AuditRepository
from api.repositories.user_repository import UserRepository

router = APIRouter()

class ProjectAdminUpdate(BaseModel):
    case_number: Optional[str] = None
    target_phone: Optional[str] = None
    target_name: Optional[str] = None
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
    project_repo = ProjectRepository(db)
    return await project_repo.get_all(skip=skip, limit=limit)

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
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_in.model_dump(exclude_unset=True)
    project = await project_repo.update(project, update_data)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(admin.id, "ADMIN_UPDATE_PROJECT", f"Admin updated project {project_id}")

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
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if refund_token:
        # Devolver token al dueño (si no es admin)
        user_repo = UserRepository(db)
        owner = await user_repo.get_by_id(project.owner_id)
        if owner and not owner.is_admin:
            owner.tokens_balance += 1

    # Eliminar carpetas
    import shutil
    from pathlib import Path
    for p in [Path("output") / str(project.id), Path("uploads") / str(project.id)]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    await project_repo.delete(project)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(admin.id, "ADMIN_DELETE_PROJECT", f"Admin deleted project {project_id}. Refunded token: {refund_token}")

    await db.commit()
    return None
