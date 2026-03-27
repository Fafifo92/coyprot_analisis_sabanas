from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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
