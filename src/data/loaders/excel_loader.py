"""
Cargador de archivos Excel y CSV con detección automática de hojas.

Implementa el patrón Strategy a través de la interfaz IDataLoader.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config.constants import (
    CALL_TYPE_DATA,
    CALL_TYPE_INCOMING,
    CALL_TYPE_OUTGOING,
    CALL_TYPE_UNKNOWN,
    COL_CALL_TYPE,
    COL_CELL_ID,
    COL_CELL_NAME,
    COL_LAC,
    COL_LATITUDE,
    COL_LONGITUDE,
    COL_ORIGINATOR,
    COL_RECEIVER,
    INTERNET_DATA_RECEIVER,
)

logger = logging.getLogger(__name__)

# Extensiones soportadas por este cargador
_SUPPORTED_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv"})

# Palabras clave para detección automática de tipo de hoja
_KEYWORDS_DATA = ("dato",)
_KEYWORDS_INCOMING = ("entrant", "incoming")
_KEYWORDS_OUTGOING = ("salient", "outgoing")

# Mapeo de columnas conocidas en hojas de datos de internet
_DATA_SHEET_COLUMN_MAP: dict[str, str] = {
    "numero": COL_ORIGINATOR,
    "fecha_trafico": "fecha_hora",
    "tipo_cdr": COL_CALL_TYPE,
    "latitud": COL_LATITUDE,
    "longitud": COL_LONGITUDE,
    "cell_identity_decimal": COL_CELL_ID,
    "nombre_celda": COL_CELL_NAME,
    "location_area_code_decimal": COL_LAC,
}

# Mapeo de columnas conocidas en hojas de llamadas (entrantes/salientes)
# Estandariza coordenadas e identifiers al mismo espacio de nombres interno
# que usa _read_data_sheet, para que pd.concat las fusione en una sola columna.
_CALL_SHEET_COLUMN_MAP: dict[str, str] = {
    "latitud": COL_LATITUDE,              # → "latitud_n"
    "longitud": COL_LONGITUDE,            # → "longitud_w"
    "nombre_celda_inicio": COL_CELL_NAME, # → "nombre_celda"
    "celda_inicio_llamada": COL_CELL_ID,  # → "cell_identity_decimal"
    "lac_inicio_llamada": COL_LAC,        # → "lac"
    "fecha_hora_inicio_llamada": "fecha_hora",
}


class ExcelLoader:
    """
    Carga archivos Excel (.xlsx/.xls) y CSV buscando hojas de
    entrantes, salientes y datos de internet.

    Implementa IDataLoader.
    """

    def can_load(self, path: Path) -> bool:
        return path.suffix.lower() in _SUPPORTED_EXTENSIONS

    def load(self, path: Path) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        Carga el archivo y devuelve un DataFrame crudo consolidado.

        Returns:
            (DataFrame, None) en caso de éxito, o (None, mensaje_error) si falla.
        """
        if not path.exists():
            return None, f"El archivo no existe: {path}"

        try:
            if path.suffix.lower() == ".csv":
                return self._load_csv(path)
            return self._load_excel(path)
        except Exception as exc:
            logger.exception("Error inesperado al cargar %s", path)
            return None, str(exc)

    def load_sheets_raw(
        self, path: Path
    ) -> tuple[Optional[dict[str, pd.DataFrame]], Optional[str]]:
        """
        Carga todas las hojas del Excel sin procesamiento automático.

        Devuelve un dict {nombre_hoja: DataFrame_crudo} para que el usuario
        pueda asignar tipo y mapear columnas por hoja.

        Returns:
            (dict, None) en caso de éxito, o (None, mensaje_error) si falla.
        """
        if not path.exists():
            return None, f"El archivo no existe: {path}"

        try:
            if path.suffix.lower() == ".csv":
                df, err = self._load_csv(path)
                if df is None:
                    return None, err
                return {"CSV": df}, None

            xl = pd.ExcelFile(path)
            sheets: dict[str, pd.DataFrame] = {}
            for name in xl.sheet_names:
                try:
                    df = pd.read_excel(path, sheet_name=name, dtype=str)
                    df.dropna(how="all", inplace=True)
                    if not df.empty:
                        sheets[name] = df
                except Exception as exc:
                    logger.warning("Error leyendo hoja '%s': %s", name, exc)

            if not sheets:
                return None, "No se encontraron hojas con datos en el archivo."

            return sheets, None
        except Exception as exc:
            logger.exception("Error inesperado al cargar %s", path)
            return None, str(exc)

    # ── Excel ─────────────────────────────────────────────────────────────────

    def _load_excel(self, path: Path) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        xl = pd.ExcelFile(path)
        sheets = {name.lower().strip(): name for name in xl.sheet_names}

        frames: list[pd.DataFrame] = []

        for key, real_name in sheets.items():
            if any(kw in key for kw in _KEYWORDS_DATA):
                frame = self._read_data_sheet(path, real_name)
            elif any(kw in key for kw in _KEYWORDS_INCOMING):
                frame = self._read_call_sheet(path, real_name, CALL_TYPE_INCOMING)
            elif any(kw in key for kw in _KEYWORDS_OUTGOING):
                frame = self._read_call_sheet(path, real_name, CALL_TYPE_OUTGOING)
            else:
                continue

            if frame is not None:
                frames.append(frame)

        if not frames:
            logger.info("Sin hojas específicas detectadas. Leyendo primera hoja.")
            df = pd.read_excel(path, sheet_name=0, dtype=str)
            df.dropna(how="all", inplace=True)
            df.columns = df.columns.str.lower().str.strip()
            if COL_CALL_TYPE not in df.columns:
                df[COL_CALL_TYPE] = CALL_TYPE_UNKNOWN
            return df, None

        df = pd.concat(frames, ignore_index=True, sort=False)
        df = df.loc[:, ~df.columns.duplicated()]
        return df, None

    def _read_call_sheet(
        self, path: Path, sheet_name: str, call_type: str
    ) -> Optional[pd.DataFrame]:
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
            df.dropna(how="all", inplace=True)
            df.columns = df.columns.str.lower().str.strip()

            # Estandarizar coordenadas y nombres de celda al mismo espacio
            # de nombres interno que usa _read_data_sheet, para que pd.concat
            # los fusione en una sola columna sin duplicados.
            rename_map = {
                k: v for k, v in _CALL_SHEET_COLUMN_MAP.items() if k in df.columns
            }
            if rename_map:
                df.rename(columns=rename_map, inplace=True)

            df[COL_CALL_TYPE] = call_type
            logger.debug("Hoja '%s' cargada (%d filas).", sheet_name, len(df))
            return df
        except Exception as exc:
            logger.warning("Error leyendo hoja '%s': %s", sheet_name, exc)
            return None

    def _read_data_sheet(
        self, path: Path, sheet_name: str
    ) -> Optional[pd.DataFrame]:
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
            df.dropna(how="all", inplace=True)

            # Mapeo insensible a mayúsculas
            cols_lower = {c.lower().strip(): c for c in df.columns}
            rename_map = {
                cols_lower[k]: v
                for k, v in _DATA_SHEET_COLUMN_MAP.items()
                if k in cols_lower
            }
            df.rename(columns=rename_map, inplace=True)
            df.columns = df.columns.str.lower().str.strip()

            if COL_CALL_TYPE not in df.columns:
                df[COL_CALL_TYPE] = CALL_TYPE_DATA
            else:
                df[COL_CALL_TYPE] = df[COL_CALL_TYPE].fillna(CALL_TYPE_DATA)

            if COL_RECEIVER not in df.columns:
                df[COL_RECEIVER] = INTERNET_DATA_RECEIVER

            logger.debug(
                "Hoja de DATOS '%s' cargada (%d filas).", sheet_name, len(df)
            )
            return df
        except Exception as exc:
            logger.warning("Error leyendo hoja de DATOS '%s': %s", sheet_name, exc)
            return None

    # ── CSV ───────────────────────────────────────────────────────────────────

    def _load_csv(self, path: Path) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8-sig")
                if not df.empty:
                    df.dropna(how="all", inplace=True)
                    df.columns = df.columns.str.lower().str.strip()
                    if COL_CALL_TYPE not in df.columns:
                        df[COL_CALL_TYPE] = CALL_TYPE_UNKNOWN
                    return df, None
            except Exception:
                continue
        return None, "No se pudo leer el archivo CSV con ningún separador conocido."
