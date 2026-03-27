import sys
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from config.api_settings import get_api_settings
from db.session import engine, Base, get_db
from sqlalchemy import text
from api.routers import auth, admin, projects, files, analysis, downloads, admin_projects, ftp
from api.routers.web import pages

logger = logging.getLogger(__name__)

# Configuramos el logging básico para la API
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # En desarrollo/fase 1 creamos las tablas automáticamente
    # En producción esto se hace con Alembic
    async with engine.begin() as conn:
        logger.info("Verificando/Creando tablas de Base de Datos...")
        await conn.run_sync(Base.metadata.create_all)

        # Parche de migración manual para SQLite local del usuario
        # Añade la nueva columna 'result_ftp_url' si no existía antes de la Fase 3.
        if get_api_settings().DATABASE_URL.startswith("sqlite"):
            try:
                await conn.execute(text("ALTER TABLE projects ADD COLUMN result_ftp_url VARCHAR"))
                logger.info("Migración aplicada: Columna 'result_ftp_url' agregada.")
            except Exception as e:
                # Si falla es porque la columna ya existe, lo ignoramos de forma segura
                pass

    yield

    logger.info("Cerrando conexiones...")
    await engine.dispose()

settings = get_api_settings()

app = FastAPI(
    title="Coyprot API - Analizador Forense",
    description="API SaaS para análisis de sábanas y geolocalización.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Ajustar en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servimos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Registramos routers
app.include_router(pages.router, tags=["Web"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(admin_projects.router, prefix="/api/admin", tags=["Admin Projects"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(files.router, prefix="/api/projects", tags=["Files"])
app.include_router(analysis.router, prefix="/api/projects", tags=["Analysis"])
app.include_router(downloads.router, prefix="/api/projects", tags=["Downloads"])
app.include_router(ftp.router, prefix="/api/projects", tags=["FTP Uploads"])

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
