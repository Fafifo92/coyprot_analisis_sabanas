from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from db.session import get_db
from db.models import User, AuditLog
from api.schemas.api_models import UserCreate, UserUpdate, UserResponse, AuditLogResponse
from api.services.security import get_current_admin, get_password_hash

router = APIRouter()

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(User).filter(User.username == user_in.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username,
        hashed_password=hashed_password,
        is_admin=user_in.is_admin,
        tokens_balance=user_in.tokens_balance,
        must_change_password=True,
        is_active=True
    )
    db.add(new_user)

    audit = AuditLog(user_id=admin.id, action="ADMIN_CREATE_USER", details=f"Created {user_in.username}")
    db.add(audit)

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
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        user.hashed_password = get_password_hash(update_data["password"])
        user.must_change_password = True # Fuerza a que la cambie
        del update_data["password"]

    for key, value in update_data.items():
        setattr(user, key, value)

    audit = AuditLog(user_id=admin.id, action="ADMIN_UPDATE_USER", details=f"Updated user_id {user_id}")
    db.add(audit)

    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False # Soft delete / Bloqueo

    audit = AuditLog(user_id=admin.id, action="ADMIN_BLOCK_USER", details=f"Blocked user_id {user_id}")
    db.add(audit)

    await db.commit()
    return None

@router.get("/audit", response_model=List[AuditLogResponse])
async def list_audit_logs(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()
