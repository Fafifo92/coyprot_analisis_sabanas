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
from db.models import Project, ProjectFile, ProjectAttachment
from core.models import ReportConfig, CaseMetadata, PdfExportConfig, RouteMapMode
from services.data_processing_service import DataProcessingService
from services.geocoding_service import GeocodingService
from reports.report_generator import ReportGenerator
import phonenumbers

logger = logging.getLogger(__name__)
settings = get_api_settings()

# Engine Síncrono exclusivo para el Worker
SYNC_DB_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql").replace("sqlite+aiosqlite", "sqlite")
sync_engine = create_engine(SYNC_DB_URL, connect_args={"check_same_thread": False} if "sqlite" in SYNC_DB_URL else {})
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

def normalize_colombian_phone(phone_str: str) -> str:
    """
    Normaliza un número de teléfono a su formato nacional colombiano de 10 dígitos.
    Intenta usar la librería phonenumbers de Google; si falla, usa heurística simple.
    """
    if not phone_str or pd.isna(phone_str):
        return ""

    phone_str = str(phone_str).strip()

    # 1. Intentar con phonenumbers (Google lib)
    try:
        # Asumimos que si no tiene prefijo, es de Colombia ("CO")
        parsed = phonenumbers.parse(phone_str, "CO")
        if phonenumbers.is_valid_number(parsed):
            # Formato nacional sin espacios (ej: 3001234567)
            nat_format = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
            return "".join(filter(str.isdigit, nat_format))
    except Exception:
        pass # Fallback a heurística

    # 2. Heurística (limpiar todo menos números)
    s = ''.join(filter(str.isdigit, phone_str))

    # Si tiene 12 dígitos y empieza con 57, quitamos el 57
    if len(s) == 12 and s.startswith("57"):
        return s[2:]

    # Si tiene más de 10 dígitos, tomamos los últimos 10 (común en Colombia)
    if len(s) > 10:
        return s[-10:]

    return s

@shared_task(name="analyze_project_task", bind=True, max_retries=3)
def analyze_project_task(self, project_id: int):
    """
    Tarea Celery que se encarga del procesamiento de datos pesados:
    1. Cargar las sábanas de excel
    2. Geocodificar
    3. Validar objetivo (Anti-Abuso)
    4. Generar Reporte HTML (Rápido)
    """
    logger.info(f"Worker de Celery inició análisis (Fase HTML) para el Proyecto ID: {project_id}")

    with SyncSessionLocal() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"Proyecto {project_id} no existe en la BD.")
            return "Project not found"

        project.status = "PROCESSING"
        project.error_message = None # Resetear errores previos
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

            # --- Validar Anti-Abuso con Advertencia y Normalización Estricta ---
            if "originador" in df_final.columns and "receptor" in df_final.columns:
                # Normalizamos toda la columna usando pandas vectorizado y phonenumbers
                originators = set(df_final["originador"].dropna().apply(normalize_colombian_phone).unique())
                receivers = set(df_final["receptor"].dropna().apply(normalize_colombian_phone).unique())
                target_normalized = normalize_colombian_phone(project.target_phone)

                # Ignoramos strings vacíos por si acaso
                originators.discard("")
                receivers.discard("")

                if target_normalized and target_normalized not in originators and target_normalized not in receivers:
                    logger.warning(f"ADVERTENCIA ANTI-ABUSO: El teléfono {project.target_phone} (normalizado: {target_normalized}) no aparece en los registros.")
                    # Agregamos el warning al proyecto, pero NO fallamos el análisis.
                    project.error_message = f"Warning Anti-Abuso: El teléfono objetivo declarado ({project.target_phone}) no coincide con ningún registro ('Originador' ni 'Receptor') en los Excel analizados. El informe se generó bajo su responsabilidad."

            # Guardado del DataFrame (Caché para futura generación de PDF a demanda)
            output_dir = Path("output") / str(project.id)
            output_dir.mkdir(parents=True, exist_ok=True)
            df_final.to_pickle(output_dir / "analyzed_df.pkl")

            # --- Generación de Reporte HTML (Rápido) ---
            project.status = "GENERATING_HTML"
            db.commit()

            report_cfg = _prepare_report_config(project, db, project_id)

            report_gen = ReportGenerator(geocoding_service=geo_svc)

            # Ajustar ruta de salida al proyecto específico
            import os
            original_out_dir = app_settings.output_dir
            app_settings.output_dir = Path("output") / str(project.id)

            base_dir = report_gen.generate(df_final, report_cfg)
            app_settings.output_dir = original_out_dir

            html_path = base_dir / "reports" / f"{report_cfg.safe_name}.html"

            project.result_html_path = str(html_path)
            project.status = "COMPLETED_HTML" # Nuevo estado intermedio
            db.commit()

            logger.info(f"Worker de Celery finalizó proyecto {project_id} (HTML OK).")
            return f"Proyecto {project_id} procesado con HTML interactivo listo."

        except Exception as e:
            logger.exception(f"Error procesando proyecto {project_id}")
            project.status = "FAILED"
            project.error_message = str(e)
            db.commit()
            raise self.retry(exc=e, countdown=60)

@shared_task(name="generate_pdf_task", bind=True, max_retries=2)
def generate_pdf_task(self, project_id: int):
    """
    Tarea Celery separada que genera el PDF pesado a demanda.
    Lee el DataFrame ya procesado de la caché (disco).
    """
    logger.info(f"Worker de Celery inició generación de PDF para el Proyecto ID: {project_id}")

    with SyncSessionLocal() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return "Project not found"

        # El HTML ya debe estar generado para saber la ruta base
        if not project.result_html_path:
            project.error_message = "Debe generarse el HTML primero."
            db.commit()
            return

        project.status = "GENERATING_PDF"
        db.commit()

        try:
            output_dir = Path("output") / str(project.id)
            pkl_path = output_dir / "analyzed_df.pkl"

            if not pkl_path.exists():
                raise Exception("No se encontró la caché de datos. Re-inicie el análisis primero.")

            df_final = pd.read_pickle(pkl_path)

            base_dir = Path(project.result_html_path).parent.parent

            report_cfg = _prepare_report_config(project, db, project_id)

            # Instanciar el servicio de geocodificación (solo por si lo pide el PDF builder para referencias, aunque los datos ya vengan con coordenadas)
            geo_svc = GeocodingService.from_paths(
                cell_db_path=app_settings.cell_db_path,
                muni_db_path=app_settings.municipalities_db_path
            )

            from reports.builders.pdf_builder import PdfReportBuilder
            from config.constants import COL_CALL_TYPE, PDF_MAP_DIR_NAME
            from reports.builders.static_map_builder import StaticLocationMapBuilder, StaticRouteMapBuilder
            from reports.integrity import write_sha256_companion

            pdf_cfg = PdfExportConfig(route_map_mode=RouteMapMode.CONSOLIDATED)
            static_maps_dir = base_dir / PDF_MAP_DIR_NAME
            static_maps_dir.mkdir(parents=True, exist_ok=True)

            # Separar datos de llamadas vs datos de internet
            mask_data = False
            if COL_CALL_TYPE in df_final.columns:
                mask_data = df_final[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")
                df_calls = df_final[~mask_data].copy()
                df_data = df_final[mask_data].copy()
            else:
                df_calls = df_final.copy()
                df_data = pd.DataFrame() # Vacío

            try:
                # Generar imágenes pesadas con Kaleido/Plotly
                StaticLocationMapBuilder.build(df_calls, static_maps_dir / "mapa_ubicaciones.png", aliases=report_cfg.aliases)
                if not df_data.empty:
                    StaticRouteMapBuilder.build_consolidated(df_data, static_maps_dir / "ruta_consolidada.png", aliases=report_cfg.aliases)
            except Exception as plot_err:
                logger.warning(f"Mapas estáticos omitidos en PDF: {plot_err}")

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

            # Integridad SHA-256 Forense
            write_sha256_companion(pdf_path)

            project.result_pdf_path = str(pdf_path)
            project.status = "COMPLETED_ALL"
            db.commit()

            logger.info(f"Worker de Celery finalizó PDF para proyecto {project_id}.")
            return f"Proyecto {project_id} procesado con PDF listo."

        except Exception as e:
            logger.exception(f"Error generando PDF para proyecto {project_id}")
            # Regresamos a COMPLETED_HTML si el PDF falla, para no perder acceso al HTML
            project.status = "COMPLETED_HTML"
            project.error_message = f"Error al generar PDF: {str(e)}"
            db.commit()
            raise self.retry(exc=e, countdown=60)

def _prepare_report_config(project: Project, db, project_id: int) -> ReportConfig:
    import re
    from core.models import PdfAttachment

    safe_case_number = re.sub(r'[<>:"/\\|?*]', '_', str(project.case_number))

    # Combina el alias por defecto del objetivo con los guardados por el usuario
    final_aliases = {project.target_phone: project.target_name or "Objetivo Principal"}
    if project.aliases:
        final_aliases.update(project.aliases)

    # Recuperar y mapear adjuntos de la DB a PdfAttachment models
    db_atts = db.query(ProjectAttachment).filter(ProjectAttachment.project_id == project_id).all()
    pdf_attachments = [PdfAttachment(category=a.category, source_path=Path(a.file_path)) for a in db_atts]

    return ReportConfig(
        report_name=f"Caso_{safe_case_number}",
        include_letterhead=True,
        upload_ftp=False,
        aliases=final_aliases,
        case_metadata=CaseMetadata(
            fields={
                "Número de Caso": project.case_number,
                "Teléfono Objetivo": project.target_phone,
                "Nombre/Alias": project.target_name or "N/A",
                "Periodo Evaluado": project.period or "N/A"
            }
        ),
        pdf_attachments=pdf_attachments
    )
