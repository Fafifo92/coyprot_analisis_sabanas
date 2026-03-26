import sys
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from config.api_settings import get_api_settings
from db.session import engine, Base, get_db
from api.routers import auth, admin, projects, files, analysis

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

# Registramos routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(files.router, prefix="/api/projects", tags=["Files"])
app.include_router(analysis.router, prefix="/api/projects", tags=["Analysis"])

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
