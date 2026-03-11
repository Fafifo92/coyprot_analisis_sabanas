"""
Builder de mapas geoespaciales.

Genera mapas Folium (cluster/calor) y Plotly (animación de recorrido).
Implementa IReportBuilder para cada tipo de mapa.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import folium
import pandas as pd
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
    """Genera mapa interactivo de recorrido usando Leaflet + MarkerCluster.

    Muestra TODOS los registros de datos de internet sin deduplicación,
    con navegación por día y filtro por hora.
    """

    def build(
        self,
        df: pd.DataFrame,
        output_path: Path,
        aliases: dict[str, str] | None = None,
    ) -> None:
        logger.info("Generando mapa de recorrido (Leaflet): %s", output_path)
        clean = _clean_for_maps(df)

        if clean.empty or COL_DATETIME not in clean.columns:
            logger.warning("Sin datos suficientes para mapa de recorrido.")
            return

        clean = clean.sort_values(by=COL_DATETIME)

        # Columnas auxiliares para agrupar por día
        # Nota: no usar prefijo _ porque itertuples() no expone esos atributos
        dt_parsed = pd.to_datetime(clean[COL_DATETIME], errors="coerce")
        clean["aux_date"] = dt_parsed.dt.date
        clean["aux_time"] = dt_parsed.dt.strftime("%H:%M:%S").fillna("--:--")
        clean["aux_hour"] = dt_parsed.dt.hour.fillna(0).astype(int)

        # Construir estructura agrupada por día
        days_data: list[dict] = []
        for date_val, group in clean.groupby("aux_date", sort=True):
            group_sorted = group.sort_values(COL_DATETIME).reset_index(drop=True)
            dt = pd.Timestamp(date_val)
            label = f"{dt.day} de {_MESES_ES[dt.month]} de {dt.year}"

            points: list[dict] = []
            for seq, row in enumerate(group_sorted.itertuples(index=False), start=1):
                cell_name = str(getattr(row, COL_CELL_NAME, ""))
                if cell_name in ("nan", "None", ""):
                    cell_name = "Ubicacion de Datos"
                cell_id = str(getattr(row, COL_CELL_ID, ""))
                if cell_id in ("nan", "None", "0", "0.0", ""):
                    cell_id = ""

                points.append({
                    "lat": round(float(getattr(row, COL_LATITUDE)), 6),
                    "lon": round(float(getattr(row, COL_LONGITUDE)), 6),
                    "time": getattr(row, "aux_time"),
                    "hour": int(getattr(row, "aux_hour")),
                    "cell": cell_name,
                    "cellId": cell_id,
                    "seq": seq,
                })

            days_data.append({
                "label": label,
                "date": str(date_val),
                "count": len(points),
                "points": points,
            })

        # Centro y zoom para encuadrar todos los puntos
        lat_min = float(clean[COL_LATITUDE].min())
        lat_max = float(clean[COL_LATITUDE].max())
        lon_min = float(clean[COL_LONGITUDE].min())
        lon_max = float(clean[COL_LONGITUDE].max())
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2

        span = max(lat_max - lat_min, lon_max - lon_min, 0.001)
        if span >= 10:
            zoom = 5
        elif span >= 5:
            zoom = 6
        elif span >= 2:
            zoom = 7
        elif span >= 1:
            zoom = 8
        elif span >= 0.5:
            zoom = 9
        else:
            zoom = 11

        total_points = sum(d["count"] for d in days_data)

        route_json = json.dumps({
            "days": days_data,
            "meta": {
                "centerLat": round(center_lat, 6),
                "centerLon": round(center_lon, 6),
                "zoom": zoom,
                "totalDays": len(days_data),
                "totalPoints": total_points,
            },
        }, ensure_ascii=False)

        # Prevenir inyección de </script> en datos de celdas
        route_json = route_json.replace("</script>", r"<\/script>")

        logger.info(
            "Recorrido Leaflet: %d registros, %d dias, ~%.1f MB JSON.",
            total_points,
            len(days_data),
            len(route_json) / 1_048_576,
        )

        html_content = self._leaflet_html_template(route_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        logger.info("Mapa de recorrido Leaflet generado.")

    @staticmethod
    def _leaflet_html_template(route_data_json: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Recorrido por Datos</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"/>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;overflow:hidden}}

#controls{{
  position:absolute;top:0;left:0;right:0;z-index:1000;
  background:rgba(255,255,255,0.97);
  border-bottom:2px solid #dee2e6;
  padding:8px 14px;
  display:flex;flex-wrap:wrap;align-items:center;gap:10px;
  box-shadow:0 2px 8px rgba(0,0,0,0.1);
}}
#map{{position:absolute;top:80px;bottom:38px;left:0;right:0}}
#summary-panel{{
  position:absolute;bottom:0;left:0;right:0;height:38px;
  background:rgba(33,37,41,0.92);color:#fff;
  display:flex;align-items:center;justify-content:center;
  font-size:12.5px;gap:16px;z-index:1000;letter-spacing:0.2px;
}}

.nav-btn{{
  background:#0d6efd;color:#fff;border:none;
  padding:5px 12px;border-radius:6px;cursor:pointer;
  font-weight:600;font-size:12px;transition:background .15s;
}}
.nav-btn:hover{{background:#0b5ed7}}
.nav-btn:disabled{{background:#adb5bd;cursor:not-allowed}}

#day-select{{
  padding:4px 8px;border:1px solid #ced4da;border-radius:6px;
  font-size:12px;min-width:200px;
}}

.slider-group{{display:flex;align-items:center;gap:6px}}
.slider-group label{{font-size:11px;font-weight:700;color:#6c757d;text-transform:uppercase;white-space:nowrap}}
.slider-group input[type=range]{{width:110px;cursor:pointer}}
.slider-group .hour-val{{font-size:12px;font-weight:600;color:#0d6efd;min-width:82px;text-align:center}}

.route-toggle{{display:flex;align-items:center;gap:4px;font-size:12px;font-weight:600;color:#495057;cursor:pointer}}
.route-toggle input{{cursor:pointer}}

.day-badge{{
  font-weight:700;font-size:12px;color:#6c757d;white-space:nowrap;
}}

.route-popup{{font-size:12px;line-height:1.7}}
.route-popup b{{color:#0d6efd}}
.route-popup .seq-badge{{
  display:inline-block;background:#d62728;color:#fff;border-radius:10px;
  padding:0 7px;font-size:11px;font-weight:700;margin-left:4px;
}}

.numbered-marker{{
  background:#d62728;color:#fff;border-radius:50%;
  width:24px;height:24px;display:flex;align-items:center;
  justify-content:center;font-size:10px;font-weight:700;
  border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.35);
}}
.dot-marker{{
  background:#d62728;border-radius:50%;
  width:10px;height:10px;
  border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.3);
}}

.leaflet-popup-content{{margin:10px 14px}}
</style>
</head>
<body>

<div id="controls">
  <button class="nav-btn" id="btn-prev" onclick="prevDay()">&laquo; Ant</button>
  <select id="day-select" onchange="goToDay(parseInt(this.value))"></select>
  <button class="nav-btn" id="btn-next" onclick="nextDay()">Sig &raquo;</button>
  <span class="day-badge" id="day-counter"></span>

  <div style="flex-grow:1"></div>

  <div class="slider-group">
    <label>Desde</label>
    <input type="range" id="hour-min" min="0" max="23" value="0" oninput="updateHourFilter()">
    <label>Hasta</label>
    <input type="range" id="hour-max" min="0" max="23" value="23" oninput="updateHourFilter()">
    <span class="hour-val" id="hour-label">0:00 – 23:59</span>
  </div>

  <label class="route-toggle">
    <input type="checkbox" id="show-route" checked onchange="applyHourFilter()"> Ruta
  </label>
</div>

<div id="map"></div>
<div id="summary-panel"><span id="summary-text"></span></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
const R = {route_data_json};

var map, cluster, routeLine;
var curDay = 0;
var hMin = 0, hMax = 23;
var dayMarkers = [];

function init() {{
  map = L.map('map', {{
    center: [R.meta.centerLat, R.meta.centerLon],
    zoom: R.meta.zoom,
    zoomControl: true
  }});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19
  }}).addTo(map);

  cluster = L.markerClusterGroup({{
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
    disableClusteringAtZoom: 17,
    chunkedLoading: true
  }});
  map.addLayer(cluster);

  var sel = document.getElementById('day-select');
  R.days.forEach(function(d, i) {{
    var o = document.createElement('option');
    o.value = i;
    o.textContent = d.label + ' (' + d.count + ')';
    sel.appendChild(o);
  }});

  renderDay(0);
}}

function goToDay(i) {{
  i = parseInt(i, 10);
  if (i < 0 || i >= R.days.length) return;
  curDay = i;
  document.getElementById('day-select').value = i;
  renderDay(i);
}}
function prevDay() {{ if (curDay > 0) goToDay(curDay - 1); }}
function nextDay() {{ if (curDay < R.days.length - 1) goToDay(curDay + 1); }}

function makeIcon(seq, total) {{
  if (total > 200) {{
    return L.divIcon({{
      className: '',
      html: '<div class="dot-marker"></div>',
      iconSize: [10, 10], iconAnchor: [5, 5]
    }});
  }}
  return L.divIcon({{
    className: '',
    html: '<div class="numbered-marker">' + seq + '</div>',
    iconSize: [24, 24], iconAnchor: [12, 12]
  }});
}}

function esc(s) {{
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

function renderDay(idx) {{
  var day = R.days[idx];
  if (!day) return;

  document.getElementById('btn-prev').disabled = (idx === 0);
  document.getElementById('btn-next').disabled = (idx === R.days.length - 1);
  document.getElementById('day-counter').textContent =
    'Dia ' + (idx + 1) + ' de ' + R.days.length;

  cluster.clearLayers();
  if (routeLine) {{ map.removeLayer(routeLine); routeLine = null; }}
  dayMarkers = [];

  var total = day.points.length;
  day.points.forEach(function(pt) {{
    var m = L.marker([pt.lat, pt.lon], {{ icon: makeIcon(pt.seq, total) }});
    m._rd = pt;
    m.bindPopup(
      '<div class="route-popup">' +
      '<b>' + esc(pt.cell) + '</b><span class="seq-badge">#' + pt.seq + '</span><br>' +
      (pt.cellId ? 'ID: <b>' + esc(pt.cellId) + '</b><br>' : '') +
      'Hora: <b>' + pt.time + '</b><br>' +
      'Lat: ' + pt.lat.toFixed(6) + ', Lon: ' + pt.lon.toFixed(6) +
      '</div>', {{ maxWidth: 300 }}
    );
    dayMarkers.push(m);
  }});

  applyHourFilter();

  if (day.points.length > 0) {{
    var bounds = day.points.map(function(p) {{ return [p.lat, p.lon]; }});
    map.fitBounds(bounds, {{ padding: [40, 40], maxZoom: 15 }});
  }}
}}

function updateHourFilter() {{
  hMin = parseInt(document.getElementById('hour-min').value, 10);
  hMax = parseInt(document.getElementById('hour-max').value, 10);
  if (hMin > hMax) {{
    var t = hMin; hMin = hMax; hMax = t;
    document.getElementById('hour-min').value = hMin;
    document.getElementById('hour-max').value = hMax;
  }}
  document.getElementById('hour-label').textContent =
    hMin + ':00 – ' + hMax + ':59';
  applyHourFilter();
}}

function applyHourFilter() {{
  cluster.clearLayers();
  if (routeLine) {{ map.removeLayer(routeLine); routeLine = null; }}

  var coords = [];
  var visible = 0;

  dayMarkers.forEach(function(m) {{
    var h = m._rd.hour;
    if (h >= hMin && h <= hMax) {{
      cluster.addLayer(m);
      coords.push([m._rd.lat, m._rd.lon]);
      visible++;
    }}
  }});

  if (document.getElementById('show-route').checked && coords.length > 1) {{
    routeLine = L.polyline(coords, {{
      color: '#d62728', weight: 2.5, opacity: 0.7,
      dashArray: '8, 6'
    }}).addTo(map);
  }}

  updateSummary(visible);
}}

function updateSummary(visible) {{
  var day = R.days[curDay];
  if (!day) return;
  var txt = day.label + '  \\u2014  ' +
    day.count + ' conexiones totales  \\u2014  Mostrando: ' + visible;
  if (hMin > 0 || hMax < 23)
    txt += ' (filtro: ' + hMin + 'h \\u2013 ' + hMax + 'h)';
  document.getElementById('summary-text').textContent = txt;
}}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""
