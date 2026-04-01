"""
Constantes globales de la aplicación.

Centraliza todos los valores literales para evitar magic strings dispersos.
"""
from __future__ import annotations

from typing import Final

# ── Tipos de llamada ─────────────────────────────────────────────────────────
CALL_TYPE_INCOMING: Final[str] = "entrante"
CALL_TYPE_OUTGOING: Final[str] = "saliente"
CALL_TYPE_DATA: Final[str] = "DATOS"
CALL_TYPE_UNKNOWN: Final[str] = "desconocido"

# ── Nombres de columnas internas ─────────────────────────────────────────────
COL_ORIGINATOR: Final[str] = "originador"
COL_RECEIVER: Final[str] = "receptor"
COL_DATETIME: Final[str] = "fecha_hora"
COL_DURATION: Final[str] = "duracion"
COL_CELL_NAME: Final[str] = "nombre_celda"
COL_LATITUDE: Final[str] = "latitud_n"
COL_LONGITUDE: Final[str] = "longitud_w"
COL_LOCATION_TYPE: Final[str] = "tipo_ubicacion"  # 'EXACT', 'TOWER', 'INFERRED'
COL_CALL_TYPE: Final[str] = "tipo_llamada"
COL_CELL_ID: Final[str] = "cell_identity_decimal"
COL_LAC: Final[str] = "lac"

# ── Valores especiales ────────────────────────────────────────────────────────
UNKNOWN_NUMBER: Final[str] = "Desconocido"
UNKNOWN_LOCATION: Final[str] = "Desconocido"
INTERNET_DATA_RECEIVER: Final[str] = "INTERNET/DATOS"

# ── Categorías de documentos PDF adjuntos ────────────────────────────────────
PDF_CATEGORIES: Final[tuple[str, ...]] = (
    "Financiero",
    "Propiedades",
    "Vehículos",
    "Judicial",
    "Antecedentes",
    "Otros",
)

# ── Campos del caso (orden de aparición en el editor) ────────────────────────
DEFAULT_CASE_FIELDS: Final[tuple[str, ...]] = (
    "Cliente",
    "Ciudad",
    "Teléfono",
    "Caso",
    "Periodo",
)

# ── Tipos de hoja ─────────────────────────────────────────────────────────────
SHEET_TYPE_INCOMING: Final[str] = "Entrantes"
SHEET_TYPE_OUTGOING: Final[str] = "Salientes"
SHEET_TYPE_DATA: Final[str] = "Datos"
SHEET_TYPE_GENERIC: Final[str] = "Genérica"
SHEET_TYPE_SKIP: Final[str] = "Ignorar"

SHEET_TYPES: Final[tuple[str, ...]] = (
    SHEET_TYPE_INCOMING,
    SHEET_TYPE_OUTGOING,
    SHEET_TYPE_DATA,
    SHEET_TYPE_GENERIC,
    SHEET_TYPE_SKIP,
)

# Palabras clave para auto-detección de tipo de hoja
SHEET_DETECT_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    SHEET_TYPE_DATA: ("dato",),
    SHEET_TYPE_INCOMING: ("entrant", "incoming"),
    SHEET_TYPE_OUTGOING: ("salient", "outgoing"),
}

# ── Campos de mapeo de columnas ──────────────────────────────────────────────
# Nombre interno -> etiqueta legible para el usuario
COLUMN_MAPPING_FIELDS: Final[dict[str, str]] = {
    COL_ORIGINATOR: "Número Origen",
    COL_RECEIVER: "Número Destino",
    COL_DATETIME: "Fecha y Hora",
    COL_DURATION: "Duración (seg)",
    COL_CELL_NAME: "Nombre Celda/Antena (Opcional)",
    COL_LATITUDE: "Latitud (Decimal - Opcional)",
    COL_LONGITUDE: "Longitud (Decimal - Opcional)",
}

# Campos obligatorios en el mapeo de columnas (por tipo de hoja)
REQUIRED_MAPPING_FIELDS: Final[frozenset[str]] = frozenset(
    {COL_ORIGINATOR, COL_RECEIVER, COL_DATETIME}
)

# Para hojas de DATOS, receptor no es obligatorio (se auto-rellena)
REQUIRED_MAPPING_FIELDS_DATA: Final[frozenset[str]] = frozenset(
    {COL_ORIGINATOR, COL_DATETIME}
)

# ── Geocodificador ────────────────────────────────────────────────────────────
# Sufijos técnicos de nombres de antenas que se eliminan para obtener el nombre raíz
CELL_TECH_SUFFIXES_PATTERN: Final[str] = r"_([A-Z0-9]{1,4}|LTE|UMTS|GSM)$"

# Longitud mínima de nombre de municipio para evitar falsos positivos al inferir
MIN_MUNICIPALITY_NAME_LEN: Final[int] = 4

# ── Formato de fechas ────────────────────────────────────────────────────────
DATE_FORMATS: Final[tuple[str, ...]] = (
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y%m%d %H%M%S",
)

# Rango válido de números de serie de fecha Excel (1990-2030 aprox.)
EXCEL_SERIAL_DATE_MIN: Final[float] = 32874.0
EXCEL_SERIAL_DATE_MAX: Final[float] = 51138.0

# ── GUI ───────────────────────────────────────────────────────────────────────
GUI_THEME: Final[str] = "adapta"
GUI_GEOMETRY: Final[str] = "1000x800"
GUI_MIN_SIZE: Final[tuple[int, int]] = (750, 500)
GUI_LOG_FONT: Final[tuple[str, int]] = ("Consolas", 9)
QUEUE_POLL_MS: Final[int] = 100

# ── Nombres de archivos de mapas (deben coincidir con el template HTML) ───────
# IMPORTANTE: si se cambia un nombre aquí, debe actualizarse también en
# templates/report_template.html y viceversa.
MAP_FILE_CLUSTER: Final[str] = "mapa_agrupado.html"
MAP_FILE_HEATMAP: Final[str] = "mapa_calor.html"
MAP_FILE_ROUTE: Final[str] = "mapa_rutas.html"   # referenciado en report_template.html

# ── Reportes ─────────────────────────────────────────────────────────────────
TOP_N_CALLS: Final[int] = 5
TOP_N_CHART: Final[int] = 10
CHART_DPI: Final[int] = 100
MAP_HEATMAP_RADIUS: Final[int] = 15
MAP_HEATMAP_BLUR: Final[int] = 20

# ── PDF Report ───────────────────────────────────────────────────────────────
PDF_FONT_FAMILY: Final[str] = "Helvetica"
PDF_FONT_SIZE_BODY: Final[int] = 9
PDF_BRAND_COLOR_HEX: Final[str] = "#2c3e50"
PDF_ACCENT_COLOR_HEX: Final[str] = "#0d6efd"
PDF_STATIC_MAP_WIDTH: Final[int] = 1200
PDF_STATIC_MAP_HEIGHT: Final[int] = 800
PDF_MAP_DIR_NAME: Final[str] = "static_maps"
