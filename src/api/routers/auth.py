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
        projects_created=projects_count,
        profile_settings=current_user.profile_settings,
        global_aliases=current_user.global_aliases
    )

from api.schemas.api_models import UserSettingsUpdate
import shutil
from pathlib import Path
from fastapi import UploadFile, File

@router.patch("/me/settings", response_model=UserMeResponse)
async def update_my_settings(
    settings_in: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_repo = UserRepository(db)

    update_data = {}
    if settings_in.profile_settings is not None:
        # Merge dicts
        current_settings = current_user.profile_settings or {}
        current_settings.update(settings_in.profile_settings)
        update_data["profile_settings"] = current_settings

    if settings_in.global_aliases is not None:
        current_aliases = current_user.global_aliases or {}
        current_aliases.update(settings_in.global_aliases)
        update_data["global_aliases"] = current_aliases

    if update_data:
        from sqlalchemy.orm.attributes import flag_modified

        # The user repository's update method should handle generic dict fields
        # as long as we pass them through correctly. However, we're not using UserUpdate here directly
        # for repo validation, but passing the raw dict update.
        # Ensure your UserRepository supports updating arbitrary fields or specifically these json fields.
        for key, value in update_data.items():
            setattr(current_user, key, value)
            flag_modified(current_user, key)

        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)

    result = await db.execute(select(func.count(Project.id)).filter(Project.owner_id == current_user.id))
    projects_count = result.scalar() or 0

    return UserMeResponse(
        username=current_user.username,
        is_admin=current_user.is_admin,
        tokens_balance=current_user.tokens_balance,
        projects_created=projects_count,
        profile_settings=current_user.profile_settings,
        global_aliases=current_user.global_aliases
    )

@router.post("/me/logo")
async def upload_my_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    allowed_extensions = {".png", ".jpg", ".jpeg"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="El logo debe ser PNG o JPG.")

    if ext == ".jpeg":
        ext = ".jpg"

    user_dir = Path("uploads") / "users" / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"logo{ext}"
    file_path = user_dir / safe_filename

    # Eliminar viejo logo
    for other_ext in [".png", ".jpg"]:
        old_file = user_dir / f"logo{other_ext}"
        if old_file.exists() and old_file != file_path:
            old_file.unlink()

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"message": "Logo subido exitosamente", "filename": safe_filename}

from fastapi.responses import FileResponse

@router.get("/me/logo")
async def get_my_logo(
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint para obtener el logo del usuario.
    Se usa para evitar exponer todo el directorio /uploads públicamente.
    """
    user_dir = Path("uploads") / "users" / str(current_user.id)

    png_path = user_dir / "logo.png"
    jpg_path = user_dir / "logo.jpg"

    if png_path.exists():
        return FileResponse(png_path)
    elif jpg_path.exists():
        return FileResponse(jpg_path)

    raise HTTPException(status_code=404, detail="No se encontró un logo personalizado")
