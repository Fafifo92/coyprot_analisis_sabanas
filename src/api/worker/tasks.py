import logging
import asyncio
from pathlib import Path
import pandas as pd
from celery import shared_task

# SQLAlchemy (Síncrono para Celery Workers es más seguro y fácil que async)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.api_settings import get_api_settings
from config.settings import settings as app_settings
from db.models import Project, ProjectFile
from core.models import ReportConfig, CaseMetadata, PdfExportConfig, RouteMapMode
from services.data_processing_service import DataProcessingService
from services.geocoding_service import GeocodingService
from reports.report_generator import ReportGenerator

logger = logging.getLogger(__name__)
settings = get_api_settings()

# Engine Síncrono exclusivo para el Worker
# Reemplazamos asyncpg por psycopg2 si es Postgres
SYNC_DB_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql").replace("sqlite+aiosqlite", "sqlite")
sync_engine = create_engine(SYNC_DB_URL, connect_args={"check_same_thread": False} if "sqlite" in SYNC_DB_URL else {})
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

@shared_task(name="analyze_project_task", bind=True, max_retries=3)
def analyze_project_task(self, project_id: int):
    """
    Tarea Celery que se encarga del procesamiento de datos pesados:
    1. Cargar las sábanas de excel
    2. Geocodificar
    3. Validar objetivo
    """
    logger.info(f"Worker de Celery inició análisis para el Proyecto ID: {project_id}")

    with SyncSessionLocal() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"Proyecto {project_id} no existe en la BD.")
            return "Project not found"

        project.status = "PROCESSING"
        db.commit()

        try:
            files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()

            data_svc = DataProcessingService()
            geo_svc = GeocodingService.from_paths(
                cell_db_path=app_settings.cell_db_path,
                muni_db_path=app_settings.municipalities_db_path
            )

            accumulated_dfs = []

            for file in files:
                if file.status != "MAPPED" or not file.sheet_configs:
                    continue

                sheets, err = data_svc.load_sheets_raw(Path(file.file_path))
                if not sheets:
                    raise Exception(f"No se pudo cargar {file.filename}: {err}")

                df_processed = data_svc.process_sheets(sheets, file.sheet_configs)
                accumulated_dfs.append(df_processed)

            if not accumulated_dfs:
                raise Exception("No hay datos mapeados para procesar.")

            df_final = pd.concat(accumulated_dfs, ignore_index=True, sort=False)
            df_final = df_final.loc[:, ~df_final.columns.duplicated()]

            df_final = geo_svc.geocode_by_cell_db(df_final)
            df_final = geo_svc.geocode_by_municipality_name(df_final)

            # --- Validar Anti-Abuso con Advertencia y Normalización ---
            # Extraemos de forma robusta los últimos 10 dígitos (estándar Colombia/Celular)
            # para comparar y evitar falsos positivos (+57301... vs 301...)
            if "originador" in df_final.columns and "receptor" in df_final.columns:
                def normalize_phone(phone_str: str) -> str:
                    s = ''.join(filter(str.isdigit, str(phone_str)))
                    return s[-10:] if len(s) >= 10 else s

                originators = set(df_final["originador"].dropna().apply(normalize_phone).unique())
                receivers = set(df_final["receptor"].dropna().apply(normalize_phone).unique())
                target_normalized = normalize_phone(project.target_phone)

                if target_normalized not in originators and target_normalized not in receivers:
                    logger.warning(f"ADVERTENCIA: El teléfono {project.target_phone} (normalizado: {target_normalized}) no aparece.")
                    # Agregamos el warning al proyecto, pero no lo fallamos. Permite seguir adelante con los datos.
                    project.error_message = f"Warning Anti-Abuso: El teléfono objetivo ({project.target_phone}) no figura en ninguna columna de Originador/Receptor en la sábana mapeada. El informe se ha generado de todos modos bajo su responsabilidad."

            # --- Generación de Reportes HTML y PDF ---
            project.status = "GENERATING_REPORTS"
            db.commit()

            # Configurar la metadata del caso que será inyectada en los reportes
            report_cfg = ReportConfig(
                report_name=f"Caso_{project.case_number}",
                include_letterhead=True,
                upload_ftp=False,
                aliases={project.target_phone: project.target_name or "Objetivo Principal"},
                case_metadata=CaseMetadata(
                    fields={
                        "Número de Caso": project.case_number,
                        "Teléfono Objetivo": project.target_phone,
                        "Nombre/Alias": project.target_name or "N/A",
                        "Periodo Evaluado": project.period or "N/A"
                    }
                )
            )

            # Instanciar el Generador principal HTML
            report_gen = ReportGenerator(geocoding_service=geo_svc)

            # El ReportGenerator usa settings.output_dir por defecto,
            # ajustamos el entorno para que vaya a su carpeta de proyecto web
            import os
            original_out_dir = app_settings.output_dir
            app_settings.output_dir = Path("output") / str(project.id)

            base_dir = report_gen.generate(df_final, report_cfg)

            # Restablecer entorno por seguridad
            app_settings.output_dir = original_out_dir

            # Configurar PDF (Mapas de Ruta consolidados para que sea más rápido)
            from reports.builders.pdf_builder import PdfReportBuilder
            from config.constants import COL_CALL_TYPE, PDF_MAP_DIR_NAME
            from reports.builders.static_map_builder import StaticLocationMapBuilder, StaticRouteMapBuilder
            from reports.integrity import write_sha256_companion

            pdf_cfg = PdfExportConfig(route_map_mode=RouteMapMode.CONSOLIDATED)
            static_maps_dir = base_dir / PDF_MAP_DIR_NAME
            static_maps_dir.mkdir(parents=True, exist_ok=True)

            # Separar datos de llamadas para optimizar generación de mapas estáticos
            mask_data = df_final[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")
            df_calls = df_final[~mask_data].copy()
            df_data = df_final[mask_data].copy()

            try:
                # Generar las imágenes estáticas para incrustar en el PDF
                StaticLocationMapBuilder.build(df_calls, static_maps_dir / "mapa_ubicaciones.png", aliases=report_cfg.aliases)
                if not df_data.empty:
                    StaticRouteMapBuilder.build_consolidated(df_data, static_maps_dir / "ruta_consolidada.png", aliases=report_cfg.aliases)
            except Exception as plot_err:
                logger.warning(f"Mapas estáticos omitidos: {plot_err}")

            pdf_path = base_dir / "reports" / f"{report_cfg.safe_name}.pdf"
            pdf_builder = PdfReportBuilder()
            pdf_builder.build(
                df=df_final,
                output_path=pdf_path,
                report_config=report_cfg,
                pdf_config=pdf_cfg,
                base_dir=base_dir,
                geocoding_service=geo_svc
            )

            # Hashear el PDF forense
            write_sha256_companion(pdf_path)

            # Guardamos las rutas finales de los artefactos para servir en la API
            html_path = base_dir / "reports" / f"{report_cfg.safe_name}.html"

            project.result_html_path = str(html_path)
            project.result_pdf_path = str(pdf_path)
            project.status = "COMPLETED"
            db.commit()

            logger.info(f"Worker de Celery finalizó proyecto {project_id} (HTML/PDF OK).")
            return f"Proyecto {project_id} procesado con reportes listos."

        except Exception as e:
            logger.exception(f"Error procesando proyecto {project_id}")
            project.status = "FAILED"
            project.error_message = str(e)
            db.commit()
            raise self.retry(exc=e, countdown=60)
