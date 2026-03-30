from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from db.session import get_db
from db.models import User
from api.schemas.api_models import UserCreate, UserUpdate, UserResponse, AuditLogResponse
from api.services.security import get_current_admin
from api.repositories.user_repository import UserRepository
from api.repositories.audit_repository import AuditRepository

router = APIRouter()

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user_repo = UserRepository(db)
    return await user_repo.get_all(skip=skip, limit=limit)

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user_repo = UserRepository(db)
    existing_user = await user_repo.get_by_username(user_in.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    new_user = await user_repo.create(user_in.model_dump())

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(admin.id, "ADMIN_CREATE_USER", f"Created {user_in.username}")

    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_in.model_dump(exclude_unset=True)
    user = await user_repo.update(user, update_data)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(admin.id, "ADMIN_UPDATE_USER", f"Updated user_id {user_id}")

    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await user_repo.soft_delete(user)

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(admin.id, "ADMIN_BLOCK_USER", f"Blocked user_id {user_id}")

    await db.commit()
    return None

@router.get("/audit", response_model=List[AuditLogResponse])
async def list_audit_logs(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    audit_repo = AuditRepository(db)
    return await audit_repo.get_all(skip=skip, limit=limit)
