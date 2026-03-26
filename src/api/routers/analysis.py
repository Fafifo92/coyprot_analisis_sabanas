from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import pandas as pd
from pathlib import Path
import logging

from db.session import get_db, AsyncSessionLocal
from db.models import User, Project, ProjectFile, AuditLog
from api.services.security import get_current_user
from services.data_processing_service import DataProcessingService
from services.geocoding_service import GeocodingService
from config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Función que correrá en background (Fase 1 Background Tasks, escalable a Celery)
async def process_project_analysis(project_id: int):
    logger.info(f"Iniciando análisis background para proyecto ID: {project_id}")
    async with AsyncSessionLocal() as db:
        try:
            # Cargar proyecto y sus archivos mapeados
            result = await db.execute(
                select(Project)
                .options(selectinload(Project.files))
                .filter(Project.id == project_id)
            )
            project = result.scalars().first()

            if not project:
                return

            project.status = "PROCESSING"
            await db.commit()

            # Instanciar servicios
            data_svc = DataProcessingService()
            geo_svc = GeocodingService.from_paths(
                cell_db_path=settings.cell_db_path,
                muni_db_path=settings.municipalities_db_path
            )

            accumulated_dfs = []

            # Procesar cada archivo MAPPED
            for file in project.files:
                if file.status != "MAPPED" or not file.sheet_configs:
                    continue

                # Cargar raw data
                sheets, err = data_svc.load_sheets_raw(Path(file.file_path))
                if not sheets:
                    raise Exception(f"No se pudo cargar el archivo {file.filename}: {err}")

                # Aplicar configuraciones
                df_processed = data_svc.process_sheets(sheets, file.sheet_configs)
                accumulated_dfs.append(df_processed)

            if not accumulated_dfs:
                raise Exception("No hay datos mapeados para procesar.")

            # Combinar todo
            df_final = pd.concat(accumulated_dfs, ignore_index=True, sort=False)
            df_final = df_final.loc[:, ~df_final.columns.duplicated()]

            # Geocodificar (Estrategia 1 y 2 en cascada)
            df_final = geo_svc.geocode_by_cell_db(df_final)
            df_final = geo_svc.geocode_by_municipality_name(df_final)

            # Validar objetivo y abuso
            if "originador" in df_final.columns and "receptor" in df_final.columns:
                originators = set(df_final["originador"].dropna().astype(str).unique())
                receivers = set(df_final["receptor"].dropna().astype(str).unique())
                target = str(project.target_phone)

                # Para evitar abuso, verificamos si el target_phone está presente en los datos
                # Esto asume que al menos participó en alguna llamada o conexión de datos.
                if target not in originators and target not in receivers:
                    logger.warning(f"El teléfono objetivo {target} no figura en la sábana del proyecto {project_id}.")
                    raise Exception(f"Posible abuso/inconsistencia detectada: El teléfono objetivo ({target}) no aparece en los registros analizados.")

            # Guardar el DataFrame analizado para la siguiente fase (Generación de Reportes HTML/PDF)
            # Por ahora lo guardaremos en un pickle en disco como cache del proyecto.
            output_dir = Path("output") / str(project.id)
            output_dir.mkdir(parents=True, exist_ok=True)
            df_final.to_pickle(output_dir / "analyzed_df.pkl")

            project.status = "COMPLETED"

        except Exception as e:
            logger.exception(f"Error procesando proyecto {project_id}")
            project.status = "FAILED"
            project.error_message = str(e)
        finally:
            await db.commit()

@router.post("/{project_id}/analyze")
async def start_analysis(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.files))
        .filter(Project.id == project_id)
    )
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not any(f.status == "MAPPED" for f in project.files):
        raise HTTPException(status_code=400, detail="No hay archivos mapeados para analizar en este proyecto.")

    project.status = "QUEUED"

    audit = AuditLog(
        user_id=current_user.id,
        action="START_ANALYSIS",
        details=f"Started analysis for project {project_id}"
    )
    db.add(audit)
    await db.commit()

    # Encolar la tarea en background
    background_tasks.add_task(process_project_analysis, project_id)

    return {"message": "Análisis encolado correctamente. Consulta el estado del proyecto más tarde."}
