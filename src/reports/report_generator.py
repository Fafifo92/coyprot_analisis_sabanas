"""
Generador principal de informes HTML.

Orquesta mapas, gráficas, datos JSON y la renderización de la plantilla Jinja2.
Principio O: se puede extender agregando nuevos builders sin modificar esta clase.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from config.constants import (
    CALL_TYPE_INCOMING,
    CALL_TYPE_OUTGOING,
    COL_CALL_TYPE,
    COL_DATETIME,
    COL_LATITUDE,
    COL_LONGITUDE,
    COL_ORIGINATOR,
    COL_RECEIVER,
    MAP_FILE_CLUSTER,
    MAP_FILE_HEATMAP,
    MAP_FILE_ROUTE,
    TOP_N_CALLS,
)
from config.settings import settings
from core.exceptions import ReportGenerationError, TemplateRenderError
from core.models import ReportConfig
from reports.builders.chart_builder import (
    HourlyChartBuilder,
    TopCallsChartBuilder,
    TopLocationChartBuilder,
)
from reports.builders.map_builder import ClusterMapBuilder, HeatMapBuilder, RouteMapBuilder
from services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Orquesta la generación completa del informe HTML.

    Principio S: delega a builders especializados (mapas, gráficas).
    Principio D: recibe dependencias por inyección para facilitar testing.
    """

    def __init__(
        self,
        geocoding_service: Optional[GeocodingService] = None,
        cluster_map: Optional[ClusterMapBuilder] = None,
        heat_map: Optional[HeatMapBuilder] = None,
        route_map: Optional[RouteMapBuilder] = None,
        top_calls_chart: Optional[TopCallsChartBuilder] = None,
        hourly_chart: Optional[HourlyChartBuilder] = None,
        top_location_chart: Optional[TopLocationChartBuilder] = None,
    ) -> None:
        self._geo = geocoding_service or GeocodingService()
        self._cluster_map = cluster_map or ClusterMapBuilder()
        self._heat_map = heat_map or HeatMapBuilder()
        self._route_map = route_map or RouteMapBuilder()
        self._top_calls = top_calls_chart or TopCallsChartBuilder()
        self._hourly = hourly_chart or HourlyChartBuilder()
        self._top_location = top_location_chart or TopLocationChartBuilder()

        self._jinja_env = Environment(
            loader=FileSystemLoader(str(settings.templates_dir))
        )

    # ── API pública ───────────────────────────────────────────────────────────

    def generate(
        self,
        df: pd.DataFrame,
        config: ReportConfig,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Path:
        """
        Genera el informe completo y devuelve el directorio base de salida.

        Args:
            df: DataFrame procesado con todos los registros.
            config: Configuración del informe (nombre, alias, PDFs, etc.).

        Returns:
            Path al directorio raíz del informe generado.

        Raises:
            ReportGenerationError: si ocurre un error durante la generación.
        """
        base_dir = settings.output_dir / config.safe_name
        dirs = self._create_directories(base_dir)

        def _emit(pct: int, text: str) -> None:
            if progress_callback:
                progress_callback(pct, text)

        try:
            # 1. Separar llamadas y datos de internet
            _emit(5, "Separando llamadas y datos...")
            mask_data = df[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")
            df_calls = df[~mask_data].copy()
            df_data = df[mask_data].copy()
            logger.info(
                "Llamadas: %d | Datos internet: %d", len(df_calls), len(df_data)
            )

            # 2. Procesar adjuntos PDF
            _emit(10, "Procesando adjuntos...")
            attachments = self._process_attachments(config, dirs["data"])

            # 3. Copiar recursos estáticos
            _emit(15, "Copiando recursos...")
            self._copy_static_assets(dirs["static"], config)

            # 4. Generar mapas
            _emit(20, "Generando mapas...")
            has_coords, has_route, atypical_maps, map_flags = self._build_maps(df_calls, df_data, df, dirs["maps"], config)

            # 5. Generar gráficas
            _emit(45, "Generando gráficas...")
            self._build_charts(df_calls, dirs["graphics"], config)

            # 6. Generar data JS para gráficos interactivos
            _emit(60, "Procesando datos...")
            self._write_call_data_js(df, dirs["data"] / "call_data.js", config)

            # 7. Preparar contexto del template
            _emit(75, "Preparando informe...")
            context = self._build_template_context(
                df_calls, config, has_coords, has_route, attachments, atypical_maps, map_flags
            )

            # 8. Renderizar HTML
            _emit(90, "Renderizando HTML...")
            html_path = dirs["reports"] / "informe_llamadas.html"
            self._render_template(context, html_path)

            _emit(100, "Informe completado")
            logger.info("Informe generado: %s", html_path)
            return base_dir

        except TemplateRenderError:
            raise
        except Exception as exc:
            logger.exception("Error generando informe")
            raise ReportGenerationError(str(exc)) from exc

    # ── Directorios ───────────────────────────────────────────────────────────

    @staticmethod
    def _create_directories(base: Path) -> dict[str, Path]:
        dirs = {
            "reports": base / "reports",
            "maps": base / "maps",
            "graphics": base / "graphics",
            "data": base / "data",
            "static": base / "static",
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    # ── Adjuntos ──────────────────────────────────────────────────────────────

    @staticmethod
    def _process_attachments(
        config: ReportConfig, data_dir: Path
    ) -> list[dict[str, str]]:
        result = []
        for att in config.pdf_attachments:
            if not att.is_valid:
                continue
            try:
                shutil.copy(str(att.source_path), str(data_dir / att.filename))
                result.append({
                    "categoria": att.category,
                    "nombre": att.filename,
                    "ruta_relativa": f"../data/{att.filename}",
                })
            except Exception as exc:
                logger.warning("No se pudo copiar adjunto %s: %s", att.filename, exc)
        return result

    # ── Recursos estáticos ────────────────────────────────────────────────────

    def _copy_static_assets(self, static_dir: Path, config: ReportConfig) -> None:
        js_dir = static_dir / "assets_js"
        img_dir = static_dir / "assets_img"
        js_dir.mkdir(parents=True, exist_ok=True)
        img_dir.mkdir(parents=True, exist_ok=True)

        for js_file in ("interactive_maps.js", "interactive_charts.js"):
            src = settings.static_dir / "assets_js" / js_file
            if src.exists():
                shutil.copy(str(src), str(js_dir / js_file))

        if config.include_letterhead:
            if config.logo_type == "custom" and config.custom_logo_path and Path(config.custom_logo_path).exists():
                shutil.copy(config.custom_logo_path, str(img_dir / "logo.png"))
            elif settings.logo_path.exists():
                shutil.copy(str(settings.logo_path), str(img_dir / "logo.png"))

        if settings.info_icon_path.exists():
            shutil.copy(str(settings.info_icon_path), str(img_dir / "info.png"))

    # ── Mapas ─────────────────────────────────────────────────────────────────

    def _build_maps(
        self,
        df_calls: pd.DataFrame,
        df_data: pd.DataFrame,
        df_all: pd.DataFrame,
        maps_dir: Path,
        config: ReportConfig,
    ) -> tuple[bool, bool, list[dict], dict[str, bool]]:
        has_coords = (
            COL_LATITUDE in df_all.columns
            and df_all[COL_LATITUDE].notna().any()
        )
        has_route = False
        atypical_maps = []
        map_flags = {
            "has_entrantes_map": False,
            "has_salientes_map": False,
            "has_day_map": False,
            "has_night_map": False
        }

        if not has_coords:
            return False, False, [], map_flags

        try:
            # Independent maps for incoming and outgoing
            df_in = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_INCOMING]
            df_out = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_OUTGOING]

            if not df_in.empty and COL_LATITUDE in df_in.columns and df_in[COL_LATITUDE].notna().any():
                self._cluster_map.build(df_in, maps_dir / "mapa_entrantes.html", aliases=config.aliases)
                map_flags["has_entrantes_map"] = True
            if not df_out.empty and COL_LATITUDE in df_out.columns and df_out[COL_LATITUDE].notna().any():
                self._cluster_map.build(df_out, maps_dir / "mapa_salientes.html", aliases=config.aliases)
                map_flags["has_salientes_map"] = True

            # Map for Day and Night (using all data including internet connections)
            if "is_night" in df_all.columns:
                df_night = df_all[df_all["is_night"] == True]
                df_day = df_all[df_all["is_night"] == False]

                if not df_day.empty and COL_LATITUDE in df_day.columns and df_day[COL_LATITUDE].notna().any():
                    self._heat_map.build(df_day, maps_dir / "mapa_dia.html")
                    map_flags["has_day_map"] = True
                if not df_night.empty and COL_LATITUDE in df_night.columns and df_night[COL_LATITUDE].notna().any():
                    self._heat_map.build(df_night, maps_dir / "mapa_noche.html")
                    map_flags["has_night_map"] = True

            # Atypical Locations Maps
            if "is_atypical" in df_all.columns and df_all["is_atypical"].any():
                atypical_df = df_all[df_all["is_atypical"] == True]
                groups = atypical_df.groupby("location_group")

                for i, (group_name, group_data) in enumerate(groups):
                    if not group_data.empty and COL_LATITUDE in group_data.columns and group_data[COL_LATITUDE].notna().any():
                        filename = f"mapa_atipico_{i}.html"
                        # Include event count and specific dates for the template
                        dates = group_data[COL_DATETIME].dt.strftime('%Y-%m-%d %H:%M').unique().tolist()
                        atypical_maps.append({
                            "name": str(group_name),
                            "file": filename,
                            "count": len(group_data),
                            "dates": dates[:10] + (["..."] if len(dates) > 10 else [])
                        })
                        self._cluster_map.build(group_data, maps_dir / filename, aliases=config.aliases)

                # Sort atypical maps from most records to least records (descending)
                atypical_maps.sort(key=lambda x: x["count"], reverse=True)

        except Exception as exc:
            logger.error("Error generando mapas estáticos interactivos: %s", exc)

        if not df_data.empty and COL_LATITUDE in df_data.columns and df_data[COL_LATITUDE].notna().any():
            try:
                self._route_map.build(
                    df_data,
                    maps_dir / MAP_FILE_ROUTE,
                    aliases=config.aliases,
                )
                has_route = True
            except Exception as exc:
                logger.error("Error generando mapa de recorrido: %s", exc)

        return has_coords, has_route, atypical_maps, map_flags

    # ── Gráficas ──────────────────────────────────────────────────────────────

    def _build_charts(
        self, df_calls: pd.DataFrame, graphics_dir: Path, config: ReportConfig
    ) -> None:
        aliases = config.aliases
        df_in = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_INCOMING]
        df_out = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_OUTGOING]

        if not df_in.empty:
            self._top_calls.build(
                df_in,
                graphics_dir / "top_llamadas_recibidas.png",
                column=COL_ORIGINATOR,
                title="Top Llamadas Recibidas",
                aliases=aliases,
            )
            self._top_location.build(
                df_in,
                graphics_dir / "top_ubicacion_recibidas.png",
                number_col=COL_ORIGINATOR,
                title="Top Origen y Ubicación (Desde dónde llaman)",
                aliases=aliases,
            )

        if not df_out.empty:
            self._top_calls.build(
                df_out,
                graphics_dir / "top_llamadas_realizadas.png",
                column=COL_RECEIVER,
                title="Top Llamadas Realizadas",
                aliases=aliases,
            )
            self._top_location.build(
                df_out,
                graphics_dir / "top_ubicacion_realizadas.png",
                number_col=COL_RECEIVER,
                title="Top Destino y Ubicación (Desde dónde se llamó)",
                aliases=aliases,
            )

        self._hourly.build(df_calls, graphics_dir / "grafico_horario_llamadas.png")

    # ── Data JS ───────────────────────────────────────────────────────────────

    @staticmethod
    def _write_call_data_js(
        df: pd.DataFrame, output_path: Path, config: ReportConfig
    ) -> None:
        """Genera call_data.js con los datos para los gráficos interactivos."""
        mask = df[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")
        df_calls = df[~mask].copy()

        if df_calls.empty:
            output_path.write_text("const CALL_DATA = {};", encoding="utf-8")
            return

        has_coords = COL_LATITUDE in df_calls.columns and COL_LONGITUDE in df_calls.columns
        call_data: dict[str, list] = {}

        for row in df_calls.itertuples(index=False):
            call_type = getattr(row, COL_CALL_TYPE, "desconocido")
            origin = str(getattr(row, COL_ORIGINATOR, "Desconocido"))
            dest = str(getattr(row, COL_RECEIVER, "Desconocido"))
            key_num = dest if call_type == CALL_TYPE_OUTGOING else origin
            display = config.display_name(key_num)

            try:
                hour = getattr(row, COL_DATETIME).hour
            except Exception:
                hour = 0

            lat = getattr(row, COL_LATITUDE, None) if has_coords else None
            lon = getattr(row, COL_LONGITUDE, None) if has_coords else None

            dt = getattr(row, COL_DATETIME, None)

            is_night = bool(getattr(row, "is_night", False))
            is_atypical = bool(getattr(row, "is_atypical", False))

            call_data.setdefault(display, []).append({
                "numero": display,
                "fecha_hora": dt.isoformat() if pd.notna(dt) else "",
                "hora": hour,
                "tipo_llamada": call_type,
                "latitud": float(lat) if lat is not None and pd.notna(lat) else None,
                "longitud": float(lon) if lon is not None and pd.notna(lon) else None,
                "is_night": is_night,
                "is_atypical": is_atypical
            })

        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = "const CALL_DATA = " + json.dumps(call_data, indent=2) + ";"
        output_path.write_text(content, encoding="utf-8")

    # ── Contexto del template ─────────────────────────────────────────────────

    def _build_template_context(
        self,
        df_calls: pd.DataFrame,
        config: ReportConfig,
        has_coords: bool,
        has_route: bool,
        attachments: list[dict],
        atypical_maps: list[dict] = None,
        map_flags: dict[str, bool] = None
    ) -> dict:
        if atypical_maps is None:
            atypical_maps = []
        if map_flags is None:
            map_flags = {}
        aliases = config.aliases

        unique_nums: set[str] = set()
        for col in (COL_ORIGINATOR, COL_RECEIVER):
            if col in df_calls.columns:
                unique_nums.update(df_calls[col].dropna().astype(str).unique())

        total = len(df_calls)

        df_in = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_INCOMING]
        df_out = df_calls[df_calls[COL_CALL_TYPE] == CALL_TYPE_OUTGOING]

        total_entrantes = len(df_in)
        total_salientes = len(df_out)

        # Calculate daily average instead of per-number average
        unique_days = 1
        if not df_calls.empty and COL_DATETIME in df_calls.columns:
            days = df_calls[COL_DATETIME].dt.date.nunique()
            unique_days = days if days > 0 else 1

        avg = total / unique_days

        top_in = self._top_n(df_in, COL_ORIGINATOR, aliases, n=10)
        top_out = self._top_n(df_out, COL_RECEIVER, aliases, n=10)
        bottom_in = self._top_n(df_in, COL_ORIGINATOR, aliases, n=10, ascending=True)
        bottom_out = self._top_n(df_out, COL_RECEIVER, aliases, n=10, ascending=True)

        calls_in, calls_out, geo_map_in, geo_map_out = self._build_call_tables(df_calls, aliases, has_coords)

        dep_mun_ent: dict[str, list[str]] = {}
        dep_mun_sal: dict[str, list[str]] = {}
        for dep, muni_set in geo_map_in.items():
            dep_mun_ent[dep] = sorted(muni_set)
        for dep, muni_set in geo_map_out.items():
            dep_mun_sal[dep] = sorted(muni_set)

        return {
            "total_llamadas": total,
            "total_entrantes": total_entrantes,
            "total_salientes": total_salientes,
            "total_numeros": len(unique_nums),
            "promedio_llamadas": round(avg, 2),
            "llamadas_entrantes": calls_in,
            "llamadas_salientes": calls_out,
            "numeros_unicos": sorted(config.display_name(n) for n in unique_nums),
            "top_entrantes": top_in,
            "top_salientes": top_out,
            "bottom_entrantes": bottom_in,
            "bottom_salientes": bottom_out,
            "incluir_membrete": config.include_letterhead,
            "adjuntos": attachments,
            "datos_generales": config.case_metadata.to_dict(),
            "has_coords": has_coords,
            "has_datos_recorrido": has_route,
            "atypical_maps": atypical_maps, # defined explicitly via locals or passed as arg
            "lista_departamentos_ent": sorted(dep_mun_ent.keys()),
            "lista_departamentos_sal": sorted(dep_mun_sal.keys()),
            "mapa_dep_mun_ent": dep_mun_ent,
            "mapa_dep_mun_sal": dep_mun_sal,
            "has_atypical_locations": len(atypical_maps) > 0,
            "has_entrantes_map": map_flags.get("has_entrantes_map", False),
            "has_salientes_map": map_flags.get("has_salientes_map", False),
            "has_day_map": map_flags.get("has_day_map", False),
            "has_night_map": map_flags.get("has_night_map", False),
            "primary_color": config.primary_color,
            "secondary_color": config.secondary_color,
            "company_name": config.company_name,
            "company_address": config.company_address,
            "company_phone": config.company_phone,
            "company_email": config.company_email,
        }

    def _build_call_tables(
        self,
        df: pd.DataFrame,
        aliases: dict[str, str],
        has_coords: bool,
    ) -> tuple[dict, dict, dict[str, set], dict[str, set]]:
        calls_in: dict = {}
        calls_out: dict = {}
        geo_map_in: dict[str, set] = {}
        geo_map_out: dict[str, set] = {}

        for row in df.itertuples(index=False):
            call_type = getattr(row, COL_CALL_TYPE, "")
            origin = str(getattr(row, COL_ORIGINATOR, "Desconocido"))
            dest = str(getattr(row, COL_RECEIVER, "Desconocido"))
            o_disp = aliases.get(origin, origin) and f"{origin} ({aliases[origin]})" if origin in aliases else origin
            r_disp = aliases.get(dest, dest) and f"{dest} ({aliases[dest]})" if dest in aliases else dest

            # Geografía
            lat = getattr(row, COL_LATITUDE, None) if has_coords else None
            lon = getattr(row, COL_LONGITUDE, None) if has_coords else None
            coords_str = "N/A"
            depto, muni = "Desconocido", "Desconocido"

            if has_coords and lat is not None and pd.notna(lat) and lon is not None and pd.notna(lon):
                coords_str = f"{lat}, {lon}"
                depto, muni = self._geo.get_location(float(lat), float(lon))
                if depto not in ("Desconocido",) and muni not in ("Desconocido",):
                    if call_type == CALL_TYPE_INCOMING:
                        geo_map_in.setdefault(depto, set()).add(muni)
                    elif call_type == CALL_TYPE_OUTGOING:
                        geo_map_out.setdefault(depto, set()).add(muni)

            dt = getattr(row, COL_DATETIME, None)
            info = {
                "fecha_hora": dt,
                "duracion": getattr(row, "duracion", 0),
                "ubicacion_coords": coords_str,
                "departamento": depto,
                "municipio": muni,
            }

            if call_type == CALL_TYPE_OUTGOING:
                calls_out.setdefault(r_disp, {"llamadas": []})["llamadas"].append(info)
            elif call_type == CALL_TYPE_INCOMING:
                calls_in.setdefault(o_disp, {"llamadas": []})["llamadas"].append(info)

        return calls_in, calls_out, geo_map_in, geo_map_out

    @staticmethod
    def _top_n(
        df: pd.DataFrame, col: str, aliases: dict[str, str], n: int = TOP_N_CALLS, ascending: bool = False
    ) -> list[dict]:
        if df.empty or col not in df.columns:
            return []
        result = []
        counts = df[col].value_counts(ascending=ascending)
        # Handle cases where there might be 0 counts causing issues, just take the top/bottom n
        for num, count in counts.head(n).items():
            if pd.isna(num) or num == "" or count == 0: continue
            alias = aliases.get(str(num))
            display = f"{num} ({alias})" if alias else str(num)
            result.append({"nombre": display, "frecuencia": count})
        return result

    # ── Renderizado ───────────────────────────────────────────────────────────

    def _render_template(self, context: dict, output_path: Path) -> None:
        try:
            template = self._jinja_env.get_template("report_template.html")
            html = template.render(**context)
            output_path.write_text(html, encoding="utf-8")
        except Exception as exc:
            raise TemplateRenderError(f"Error renderizando plantilla: {exc}") from exc
