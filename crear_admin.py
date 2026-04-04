import asyncio
import os
import sys
import secrets
from pathlib import Path

# Añadir src/ al PYTHONPATH en runtime
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
os.environ["PYTHONPATH"] = str(_SRC_DIR)

from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal, engine, Base
from db.models import User
from api.services.security import get_password_hash

async def create_superadmin():
    async with engine.begin() as conn:
        print("Verificando/Creando tablas de Base de Datos...")
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Configuración desde variables de entorno con valores por defecto seguros
        admin_username = os.environ.get("ADMIN_USERNAME", "coyprot-admin")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        is_generated = False
        if not admin_password:
            admin_password = secrets.token_urlsafe(16)
            is_generated = True

        # Check if already exists
        from sqlalchemy.future import select
        result = await db.execute(select(User).filter(User.username == admin_username))
        user = result.scalars().first()

        if user:
            print(f"El usuario '{admin_username}' ya existe.")
            return

        new_admin = User(
            username=admin_username,
            hashed_password=get_password_hash(admin_password),
            ftp_prefix="ADMIN",
            is_admin=True,
            is_active=True,
            must_change_password=True if is_generated else False,
            tokens_balance=0  # Admins tienen uso ilimitado por diseño, balance no importa
        )
        db.add(new_admin)
        await db.commit()

        print(f"Superadmin creado exitosamente:")
        print(f"Usuario: {admin_username}")
        print(f"Contraseña: {admin_password}")
        if is_generated:
            print("⚠️ GUARDE ESTA CONTRASEÑA. El usuario deberá cambiarla al iniciar sesión.")

if __name__ == "__main__":
    asyncio.run(create_superadmin())
