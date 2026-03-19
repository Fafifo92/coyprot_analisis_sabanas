"""
Builder de mapas estáticos para embeber en PDF.

Genera imágenes PNG usando Plotly + Kaleido (sin necesidad de API token).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config.constants import (
    CALL_TYPE_INCOMING,
    CALL_TYPE_OUTGOING,
    COL_CALL_TYPE,
    COL_CELL_NAME,
    COL_DATETIME,
    COL_LATITUDE,
    COL_LONGITUDE,
    PDF_STATIC_MAP_HEIGHT,
    PDF_STATIC_MAP_WIDTH,
)

logger = logging.getLogger(__name__)


def _compute_zoom(lats: pd.Series, lons: pd.Series) -> int:
    """Calcula un nivel de zoom apropiado según la extensión geográfica."""
    lat_min, lat_max = float(lats.min()), float(lats.max())
    lon_min, lon_max = float(lons.min()), float(lons.max())
    span = max(lat_max - lat_min, lon_max - lon_min, 0.001)

    if span >= 10:
        return 5
    elif span >= 5:
        return 6
    elif span >= 2:
        return 7
    elif span >= 1:
        return 8
    elif span >= 0.5:
        return 9
    elif span >= 0.2:
        return 10
    elif span >= 0.05:
        return 12
    elif span >= 0.01:
        return 13
    else:
        return 14


def _reverse_geocode(lat: float, lon: float) -> str:
    """Obtiene ciudad/municipio mediante geocodificación inversa (Nominatim).

    Retorna cadena vacía si no puede resolver.
    """
    try:
        import urllib.request
        import json

        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lon}&format=json&zoom=10"
            f"&accept-language=es"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "CoYProtAnalysis/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        addr = data.get("address", {})
        city = (
            addr.get("city")
            or addr.get("town")
            or addr.get("municipality")
            or addr.get("village")
            or addr.get("county")
            or ""
        )
        state = addr.get("state", "")
        parts = [p for p in (city, state) if p]
        return ", ".join(parts)
    except Exception:
        logger.debug("No se pudo geocodificar (%s, %s)", lat, lon)
        return ""

# Nombres de meses en español (índice 1-12)
_MESES_ES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _clean_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra filas con coordenadas numéricas válidas."""
    if df is None or df.empty:
        return pd.DataFrame()

    required = [COL_LATITUDE, COL_LONGITUDE]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    clean = df.dropna(subset=required).copy()
    for col in required:
        clean[col] = pd.to_numeric(clean[col], errors="coerce")
    clean.dropna(subset=required, inplace=True)

    clean = clean[
        clean[COL_LATITUDE].between(-90, 90)
        & clean[COL_LONGITUDE].between(-180, 180)
    ]
    return clean


class StaticLocationMapBuilder:
    """Genera un PNG estático con las ubicaciones de llamadas."""

    @staticmethod
    def build(
        df: pd.DataFrame,
        output_path: Path,
        aliases: dict[str, str] | None = None,
    ) -> bool:
        """Genera mapa agregado de ubicaciones de llamadas.

        Retorna True si la imagen fue generada, False si no hay datos.
        """
        clean = _clean_coords(df)
        if clean.empty:
            logger.warning("Sin coordenadas para mapa de ubicaciones.")
            return False

        clean = clean.copy()
        tipo_map = {
            CALL_TYPE_INCOMING: "Entrante",
            CALL_TYPE_OUTGOING: "Saliente",
        }
        clean["tipo_display"] = (
            clean[COL_CALL_TYPE]
            .astype(str)
            .str.lower()
            .map(tipo_map)
            .fillna("Otro")
        )

        try:
            zoom = _compute_zoom(clean[COL_LATITUDE], clean[COL_LONGITUDE])
            center_lat = float(clean[COL_LATITUDE].mean())
            center_lon = float(clean[COL_LONGITUDE].mean())
            location = _reverse_geocode(center_lat, center_lon)
            loc_title = "Ubicaciones de Llamadas"
            if location:
                loc_title += f" — {location}"

            fig = px.scatter_map(
                clean,
                lat=COL_LATITUDE,
                lon=COL_LONGITUDE,
                color="tipo_display",
                color_discrete_map={
                    "Entrante": "#0d6efd",
                    "Saliente": "#28a745",
                    "Otro": "#6c757d",
                },
                opacity=0.7,
                zoom=zoom,
                title=loc_title,
            )
            fig.update_layout(
                map_style="carto-positron",
                margin=dict(l=10, r=10, t=40, b=10),
                legend_title_text="Tipo",
                font=dict(family="Helvetica, Arial, sans-serif"),
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.write_image(
                str(output_path),
                width=PDF_STATIC_MAP_WIDTH,
                height=PDF_STATIC_MAP_HEIGHT,
                engine="kaleido",
            )
            logger.info("Mapa de ubicaciones generado: %s", output_path.name)
            return True

        except Exception:
            logger.exception("Error generando mapa de ubicaciones.")
            return False


class StaticRouteMapBuilder:
    """Genera mapas estáticos de recorrido en PNG."""

    @staticmethod
    def build_daily(
        df: pd.DataFrame,
        output_dir: Path,
        aliases: dict[str, str] | None = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[tuple[str, Path]]:
        """Genera un mapa de ruta por día.

        Retorna lista de ``(label, path)`` por cada imagen generada.
        """
        clean = _clean_coords(df)
        if clean.empty or COL_DATETIME not in clean.columns:
            logger.warning("Sin datos para mapas de ruta diarios.")
            return []

        clean = clean.copy()
        dt_parsed = pd.to_datetime(clean[COL_DATETIME], errors="coerce")
        clean["_date"] = dt_parsed.dt.date
        clean = clean.sort_values(COL_DATETIME)

        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[tuple[str, Path]] = []

        day_groups = list(clean.groupby("_date", sort=True))
        total_days = len(day_groups)

        for idx, (date_val, group) in enumerate(day_groups, 1):
            if progress_callback:
                progress_callback(idx, total_days, str(date_val))
            group = group.sort_values(COL_DATETIME).reset_index(drop=True)
            dt = pd.Timestamp(date_val)
            label = f"{dt.day} de {_MESES_ES[dt.month]} de {dt.year}"
            filename = f"ruta_{date_val}.png"
            out_path = output_dir / filename

            try:
                fig = _build_route_figure(group, label)
                fig.write_image(
                    str(out_path),
                    width=PDF_STATIC_MAP_WIDTH,
                    height=PDF_STATIC_MAP_HEIGHT,
                    engine="kaleido",
                )
                results.append((label, out_path))
                logger.info("Ruta diaria generada: %s", filename)
            except Exception:
                logger.exception("Error en ruta del %s", date_val)

        return results

    @staticmethod
    def build_consolidated(
        df: pd.DataFrame,
        output_path: Path,
        aliases: dict[str, str] | None = None,
    ) -> bool:
        """Genera un mapa consolidado con todas las rutas.

        Retorna True si la imagen fue generada.
        """
        clean = _clean_coords(df)
        if clean.empty or COL_DATETIME not in clean.columns:
            logger.warning("Sin datos para mapa de ruta consolidado.")
            return False

        clean = clean.sort_values(COL_DATETIME).copy()
        dt_parsed = pd.to_datetime(clean[COL_DATETIME], errors="coerce")
        clean["_date"] = dt_parsed.dt.date.astype(str)

        try:
            fig = go.Figure()

            # Ruta por día con colores distintos
            colors_pool = [
                "#d62728", "#1f77b4", "#2ca02c", "#ff7f0e",
                "#9467bd", "#8c564b", "#e377c2", "#17becf",
            ]
            for i, (date_val, group) in enumerate(
                clean.groupby("_date", sort=True)
            ):
                group = group.sort_values(COL_DATETIME)
                color = colors_pool[i % len(colors_pool)]
                dt = pd.Timestamp(date_val)
                day_label = f"{dt.day} de {_MESES_ES[dt.month]} de {dt.year}"

                # Marcadores
                fig.add_trace(go.Scattermap(
                    lat=group[COL_LATITUDE],
                    lon=group[COL_LONGITUDE],
                    mode="markers",
                    marker=dict(size=7, color=color, opacity=0.8),
                    name=day_label,
                    hovertext=group.get(COL_CELL_NAME, ""),
                ))
                # Línea de ruta
                fig.add_trace(go.Scattermap(
                    lat=group[COL_LATITUDE],
                    lon=group[COL_LONGITUDE],
                    mode="lines",
                    line=dict(width=2, color=color),
                    showlegend=False,
                ))

            center_lat = float(clean[COL_LATITUDE].mean())
            center_lon = float(clean[COL_LONGITUDE].mean())
            zoom = _compute_zoom(clean[COL_LATITUDE], clean[COL_LONGITUDE])

            # Geocodificación inversa para el mapa consolidado
            location = _reverse_geocode(center_lat, center_lon)
            con_title = "Recorrido Consolidado de Datos"
            if location:
                con_title += f" — {location}"

            fig.update_layout(
                map_style="carto-positron",
                map_center=dict(lat=center_lat, lon=center_lon),
                map_zoom=zoom,
                margin=dict(l=10, r=10, t=40, b=10),
                title=con_title,
                font=dict(family="Helvetica, Arial, sans-serif"),
                legend=dict(
                    yanchor="top", y=0.98,
                    xanchor="left", x=0.01,
                    bgcolor="rgba(255,255,255,0.85)",
                ),
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.write_image(
                str(output_path),
                width=PDF_STATIC_MAP_WIDTH,
                height=PDF_STATIC_MAP_HEIGHT,
                engine="kaleido",
            )
            logger.info("Ruta consolidada generada: %s", output_path.name)
            return True

        except Exception:
            logger.exception("Error generando ruta consolidada.")
            return False


def _build_route_figure(group: pd.DataFrame, title: str) -> go.Figure:
    """Construye una figura Plotly de ruta para un grupo de datos."""
    fig = go.Figure()

    # Marcadores numerados
    fig.add_trace(go.Scattermap(
        lat=group[COL_LATITUDE],
        lon=group[COL_LONGITUDE],
        mode="markers+text",
        marker=dict(size=10, color="#d62728", opacity=0.85),
        text=[str(i + 1) for i in range(len(group))],
        textfont=dict(size=8, color="white"),
        hovertext=group.get(COL_CELL_NAME, ""),
        showlegend=False,
    ))

    # Línea de ruta
    fig.add_trace(go.Scattermap(
        lat=group[COL_LATITUDE],
        lon=group[COL_LONGITUDE],
        mode="lines",
        line=dict(width=2.5, color="#d62728"),
        opacity=0.7,
        showlegend=False,
    ))

    center_lat = float(group[COL_LATITUDE].mean())
    center_lon = float(group[COL_LONGITUDE].mean())
    zoom = _compute_zoom(group[COL_LATITUDE], group[COL_LONGITUDE])

    # Geocodificación inversa para obtener ciudad/municipio
    location = _reverse_geocode(center_lat, center_lon)
    full_title = f"Recorrido: {title}"
    if location:
        full_title += f" — {location}"

    fig.update_layout(
        map_style="carto-positron",
        map_center=dict(lat=center_lat, lon=center_lon),
        map_zoom=zoom,
        margin=dict(l=10, r=10, t=40, b=10),
        title=full_title,
        font=dict(family="Helvetica, Arial, sans-serif"),
    )
    return fig
