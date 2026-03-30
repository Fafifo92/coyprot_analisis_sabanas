from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.session import get_db
from db.models import User, Project
from api.schemas.api_models import Token, ChangePasswordRequest
from api.schemas.auth_models import UserMeResponse
from api.services.security import verify_password, get_password_hash, create_access_token, get_current_user
from api.repositories.user_repository import UserRepository
from api.repositories.audit_repository import AuditRepository
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Auditoria de login
    audit_repo = AuditRepository(db)
    await audit_repo.log_action(user.id, "LOGIN", f"User {user.username} logged in.")
    await db.commit()

    access_token = create_access_token(data={"sub": user.username, "is_admin": user.is_admin})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "must_change_password": user.must_change_password,
        "is_admin": user.is_admin
    }

@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    user_repo = UserRepository(db)
    await user_repo.update(current_user, {"password": data.new_password, "must_change_password": False})

    audit_repo = AuditRepository(db)
    await audit_repo.log_action(current_user.id, "CHANGE_PASSWORD", "User changed their own password")
    await db.commit()

    return {"message": "Contraseña actualizada exitosamente"}

@router.get("/me", response_model=UserMeResponse)
async def get_my_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint para obtener perfil y métricas del usuario (ej. para la barra de tokens).
    """
    result = await db.execute(select(func.count(Project.id)).filter(Project.owner_id == current_user.id))
    projects_count = result.scalar() or 0

    return UserMeResponse(
        username=current_user.username,
        is_admin=current_user.is_admin,
        tokens_balance=current_user.tokens_balance,
        projects_created=projects_count
    )
