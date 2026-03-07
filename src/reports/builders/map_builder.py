"""
Builder de mapas geoespaciales.

Genera mapas Folium (cluster/calor) y Plotly (animación de recorrido).
Implementa IReportBuilder para cada tipo de mapa.
"""
from __future__ import annotations

import logging
from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
from folium.plugins import HeatMap, MarkerCluster

from config.constants import (
    CALL_TYPE_INCOMING,
    CALL_TYPE_OUTGOING,
    COL_CALL_TYPE,
    COL_CELL_ID,
    COL_CELL_NAME,
    COL_DATETIME,
    COL_LATITUDE,
    COL_LONGITUDE,
    COL_ORIGINATOR,
    COL_RECEIVER,
    MAP_HEATMAP_BLUR,
    MAP_HEATMAP_RADIUS,
    ROUTE_MAP_FRAME_DURATION_MS,
)

logger = logging.getLogger(__name__)

# Nombres de meses en español (índice 1-12)
_MESES_ES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# CSS fix para el control de capas de Folium
_CSS_LAYER_CONTROL = """
<style>
    .leaflet-control-layers-list {
        max-height: 400px !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        padding-right: 10px !important;
    }
</style>
"""


def _clean_for_maps(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra y convierte coordenadas a numérico."""
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


class ClusterMapBuilder:
    """Genera mapa de marcadores agrupados (Folium MarkerCluster)."""

    def build(
        self,
        df: pd.DataFrame,
        output_path: Path,
        aliases: dict[str, str] | None = None,
    ) -> None:
        logger.info("Generando mapa agrupado: %s", output_path)
        clean = _clean_for_maps(df)
        if clean.empty:
            return

        aliases = aliases or {}
        center = [clean[COL_LATITUDE].mean(), clean[COL_LONGITUDE].mean()]
        mapa = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
        mapa.get_root().html.add_child(folium.Element(_CSS_LAYER_CONTROL))

        cluster_in = MarkerCluster(name="Entrantes (Azul)").add_to(mapa)
        cluster_out = MarkerCluster(name="Salientes (Verde)").add_to(mapa)
        cluster_data = MarkerCluster(name="Datos (Morado)").add_to(mapa)

        for row in clean.itertuples(index=False):
            lat = getattr(row, COL_LATITUDE)
            lon = getattr(row, COL_LONGITUDE)
            call_type = str(getattr(row, COL_CALL_TYPE, "")).lower()

            if "dato" in call_type:
                cid = str(getattr(row, COL_CELL_ID, ""))
                cell = str(getattr(row, COL_CELL_NAME, ""))
                label = (
                    f"Celda: {cid}" if cid not in ("nan", "None", "")
                    else f"Antena: {cell}" if cell not in ("nan", "None", "")
                    else "Tráfico de Datos"
                )
                cluster, color, icon = cluster_data, "purple", "globe"
            elif call_type == CALL_TYPE_OUTGOING:
                num = str(getattr(row, COL_RECEIVER, "N/A"))
                alias = aliases.get(num, "")
                label = f"{num} ({alias})" if alias else num
                cluster, color, icon = cluster_out, "green", "arrow-up"
            else:
                num = str(getattr(row, COL_ORIGINATOR, "N/A"))
                alias = aliases.get(num, "")
                label = f"{num} ({alias})" if alias else num
                cluster, color, icon = cluster_in, "blue", "arrow-down"

            popup = folium.Popup(
                f"<b>{label}</b><br>{getattr(row, COL_DATETIME, '')}<br>{call_type}",
                max_width=300,
            )
            folium.Marker(
                [lat, lon],
                popup=popup,
                icon=folium.Icon(color=color, icon=icon, prefix="fa"),
            ).add_to(cluster)

        folium.LayerControl().add_to(mapa)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mapa.save(str(output_path))


class HeatMapBuilder:
    """Genera mapa de calor (Folium HeatMap)."""

    def build(self, df: pd.DataFrame, output_path: Path, **_: object) -> None:
        logger.info("Generando mapa de calor: %s", output_path)
        clean = _clean_for_maps(df)
        if clean.empty:
            return

        center = [clean[COL_LATITUDE].mean(), clean[COL_LONGITUDE].mean()]
        mapa = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
        heat_data = clean[[COL_LATITUDE, COL_LONGITUDE]].values.tolist()
        HeatMap(heat_data, radius=MAP_HEATMAP_RADIUS, blur=MAP_HEATMAP_BLUR).add_to(mapa)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mapa.save(str(output_path))


class RouteMapBuilder:
    """Genera mapa animado de recorrido de datos de internet (Plotly).

    Agrega los registros por día y celda única para mantener el archivo
    HTML liviano (< 1 MB) incluso con cientos de miles de registros crudos.
    """

    def build(
        self,
        df: pd.DataFrame,
        output_path: Path,
        aliases: dict[str, str] | None = None,
    ) -> None:
        logger.info("Generando mapa de recorrido (Plotly): %s", output_path)
        clean = _clean_for_maps(df)

        if clean.empty or COL_DATETIME not in clean.columns:
            logger.warning("Sin datos suficientes para mapa de recorrido.")
            return

        clean = clean.sort_values(by=COL_DATETIME)
        clean["fecha"] = clean[COL_DATETIME].apply(
            lambda dt: (
                f"{dt.day} de {_MESES_ES[dt.month]} de {dt.year}"
                if pd.notna(dt) else "—"
            )
        )

        def _label(row: pd.Series) -> str:
            cell = str(row.get(COL_CELL_NAME, ""))
            cid = str(row.get(COL_CELL_ID, ""))
            if cell and cell not in ("nan", "None"):
                return f"Antena: {cell}"
            if cid and cid not in ("nan", "None", "0", "0.0"):
                return f"Celda: {cid}"
            return "Ubicación de Datos"

        clean["_main_label"] = clean.apply(_label, axis=1)
        clean["_cell_id"] = (
            clean.get(COL_CELL_ID, pd.Series("", index=clean.index))
            .fillna("")
            .astype(str)
            .replace(["nan", "None", "0", "0.0"], "")
        )

        # ── Reducir peso: un punto por (día × celda única) ────────────────────
        # Antes: 1 frame por timestamp → 100 k frames con toda la data = 38 MB
        # Ahora: 1 frame por día       → ~90 frames con celdas únicas   < 1 MB
        if COL_CELL_NAME in clean.columns and clean[COL_CELL_NAME].notna().any():
            dedup_key = ["fecha", COL_CELL_NAME]
        else:
            clean["_lat_r"] = clean[COL_LATITUDE].round(4)
            clean["_lon_r"] = clean[COL_LONGITUDE].round(4)
            dedup_key = ["fecha", "_lat_r", "_lon_r"]

        plot_df = (
            clean.drop_duplicates(subset=dedup_key, keep="first")
            .sort_values(["fecha", COL_DATETIME])
            .reset_index(drop=True)
        )

        # Orden cronológico de los períodos (el strftime español no ordena alfab.)
        period_order = clean.drop_duplicates("fecha", keep="first")["fecha"].tolist()

        # Número de orden dentro del día (1, 2, 3…) — str obligatorio para Plotly text
        plot_df["_seq"] = (plot_df.groupby("fecha").cumcount() + 1).astype(str)

        # Hora de la primera aparición de esa celda en el día
        plot_df["_hora"] = (
            pd.to_datetime(plot_df[COL_DATETIME], errors="coerce")
            .dt.strftime("%H:%M")
            .fillna("—")
        )

        logger.info(
            "Recorrido: %d registros crudos → %d puntos únicos (%d días).",
            len(clean),
            len(plot_df),
            plot_df["fecha"].nunique(),
        )

        # Zoom inicial para encuadrar todos los puntos
        lat_span = clean[COL_LATITUDE].max() - clean[COL_LATITUDE].min()
        lon_span = clean[COL_LONGITUDE].max() - clean[COL_LONGITUDE].min()
        span = max(lat_span, lon_span, 0.001)
        if span >= 10:
            initial_zoom = 5
        elif span >= 5:
            initial_zoom = 6
        elif span >= 2:
            initial_zoom = 7
        elif span >= 1:
            initial_zoom = 8
        elif span >= 0.5:
            initial_zoom = 9
        else:
            initial_zoom = 11
        center_lat = (clean[COL_LATITUDE].max() + clean[COL_LATITUDE].min()) / 2
        center_lon = (clean[COL_LONGITUDE].max() + clean[COL_LONGITUDE].min()) / 2

        fig = px.scatter_mapbox(
            plot_df,
            lat=COL_LATITUDE,
            lon=COL_LONGITUDE,
            color_discrete_sequence=["#d62728"],
            animation_frame="fecha",
            category_orders={"fecha": period_order},
            custom_data=["_main_label", "_cell_id", "fecha", "_seq", "_hora"],
            zoom=initial_zoom,
            center=dict(lat=center_lat, lon=center_lon),
            height=900,
        )

        fig.update_traces(
            marker=dict(size=18, opacity=0.9),
            hovertemplate=self._hover_template(),
        )

        # Limpiar etiquetas y aplicar cosmética al slider SIN reemplazarlo.
        # update_layout(sliders=[...]) sustituye el slider completo borrando los steps
        # → la animación queda sin frames y no avanza. fig.layout.sliders[0].update()
        # hace un merge parcial que conserva los steps generados por Plotly Express.
        if fig.layout.sliders:
            for step in fig.layout.sliders[0].steps:
                if "=" in (step.label or ""):
                    step.label = step.label.split("=", 1)[1]
            fig.layout.sliders[0].update(**self._slider_config())

        fig.update_layout(
            mapbox_style="open-street-map",
            margin={"r": 0, "t": 40, "l": 0, "b": 0},
            showlegend=False,
            title=dict(
                text="<b>Recorrido Histórico (Datos de Internet)</b>",
                y=0.99, x=0.01, xanchor="left", yanchor="top",
                font=dict(size=16, color="#333"),
            ),
            updatemenus=[self._play_buttons()],
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(
            str(output_path),
            config={"scrollZoom": True, "displayModeBar": True, "responsive": True},
        )
        logger.info("Mapa de recorrido generado.")

    @staticmethod
    def _hover_template() -> str:
        return (
            "<div style='font-family:Segoe UI,sans-serif;background:#fff;padding:12px;"
            "border-radius:8px;border-left:5px solid #d62728;"
            "box-shadow:0 4px 12px rgba(0,0,0,.2);min-width:240px;color:#333'>"
            # Cabecera: icono + nombre celda + número de orden
            "<div style='display:flex;align-items:center;margin-bottom:8px;"
            "border-bottom:1px solid #eee;padding-bottom:8px'>"
            "<span style='font-size:22px;margin-right:8px'>📡</span>"
            "<div style='font-size:14px;font-weight:bold;color:#d62728;flex:1'>"
            "%{customdata[0]}</div>"
            "<span style='background:#d62728;color:#fff;border-radius:50%;"
            "width:26px;height:26px;display:flex;align-items:center;"
            "justify-content:center;font-size:12px;font-weight:bold;flex-shrink:0'>"
            "#%{customdata[3]}</span>"
            "</div>"
            # Fila ID
            "<div style='font-size:12px;margin-bottom:4px'>"
            "<span style='color:#666'>🆔 ID:</span> <b>%{customdata[1]}</b>"
            "</div>"
            # Fila fecha
            "<div style='font-size:12px;margin-bottom:4px'>"
            "<span style='color:#666'>📅 Fecha:</span> <b>%{customdata[2]}</b>"
            "</div>"
            # Fila hora
            "<div style='font-size:12px'>"
            "<span style='color:#666'>🕐 Hora:</span> <b>%{customdata[4]}</b>"
            "</div>"
            "</div><extra></extra>"
        )

    @staticmethod
    def _play_buttons() -> dict:
        return dict(
            type="buttons",
            showactive=False,
            x=0.05, y=0.03,
            xanchor="right", yanchor="bottom",
            bgcolor="white", bordercolor="#ccc", borderwidth=1,
            pad=dict(t=0, r=10),
            buttons=[
                dict(
                    label="▶",
                    method="animate",
                    args=[None, dict(
                        frame=dict(duration=ROUTE_MAP_FRAME_DURATION_MS, redraw=True),
                        fromcurrent=True,
                    )],
                ),
                dict(
                    label="⏸",
                    method="animate",
                    args=[[None], dict(
                        mode="immediate",
                        frame=dict(duration=0, redraw=False),
                    )],
                ),
            ],
        )

    @staticmethod
    def _slider_config() -> dict:
        return dict(
            active=0,
            yanchor="bottom", xanchor="center",
            x=0.5, y=0.02, len=0.85,
            currentvalue=dict(
                font=dict(size=20, color="#d62728", family="Arial Black"),
                prefix="📅 Día: ",
                visible=True, xanchor="center", offset=25,
            ),
            bgcolor="#ffffff", bordercolor="#666", borderwidth=1,
            pad=dict(b=10, t=50),
        )
