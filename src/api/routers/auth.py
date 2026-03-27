from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.session import get_db
from db.models import User, AuditLog
from api.schemas.api_models import Token, ChangePasswordRequest
from api.services.security import verify_password, get_password_hash, create_access_token, get_current_user
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.username == form_data.username))
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Auditoria de login
    audit = AuditLog(user_id=user.id, action="LOGIN", details=f"User {user.username} logged in.")
    db.add(audit)
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

    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.must_change_password = False

    audit = AuditLog(user_id=current_user.id, action="CHANGE_PASSWORD", details="User changed their own password")
    db.add(audit)
    await db.commit()

    return {"message": "Contraseña actualizada exitosamente"}
