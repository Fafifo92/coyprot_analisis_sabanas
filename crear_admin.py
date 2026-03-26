import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal, engine, Base
from db.models import User
from api.services.security import get_password_hash

async def create_superadmin():
    async with engine.begin() as conn:
        print("Verificando/Creando tablas de Base de Datos...")
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        admin_username = "superadmin"
        admin_password = "password123"

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
            is_admin=True,
            is_active=True,
            must_change_password=False,
            tokens_balance=9999
        )
        db.add(new_admin)
        await db.commit()
        print(f"Superadmin creado exitosamente:")
        print(f"Usuario: {admin_username}")
        print(f"Contraseña: {admin_password}")

if __name__ == "__main__":
    asyncio.run(create_superadmin())
