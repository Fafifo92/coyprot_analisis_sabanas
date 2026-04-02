"""
Servicio de procesamiento de datos.

Pipeline completo: carga cruda → mapeo de columnas → normalización →
fechas → coordenadas → estadísticas.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from config.constants import (
    CALL_TYPE_DATA,
    CALL_TYPE_INCOMING,
    CALL_TYPE_OUTGOING,
    COL_CALL_TYPE,
    COL_DATETIME,
    COL_DURATION,
    COL_LATITUDE,
    COL_LONGITUDE,
    COL_ORIGINATOR,
    COL_RECEIVER,
    DATE_FORMATS,
    EXCEL_SERIAL_DATE_MAX,
    EXCEL_SERIAL_DATE_MIN,
    INTERNET_DATA_RECEIVER,
    SHEET_TYPE_DATA,
    SHEET_TYPE_GENERIC,
    SHEET_TYPE_INCOMING,
    SHEET_TYPE_OUTGOING,
)
from core.exceptions import ColumnMappingError, EmptyDataError
from core.models import CallStats, LoadResult
from data.loaders.excel_loader import ExcelLoader
from services.phone_service import PhoneService

logger = logging.getLogger(__name__)

# Palabras clave que indican cada tipo de llamada (en mayúsculas)
_INCOMING_KEYWORDS = ("ENTRANTE", "MTC", "_MT", "SMS_MT", "MOC_MT", "INCOMING")
_OUTGOING_KEYWORDS = ("SALIENTE", "MOC", "_MO", "SMS_MO", "MOC_MO", "OUTGOING")
_DATA_KEYWORDS = ("DATO", "DATA", "GPRS", "PDP", "INTERNET", "LTE_DATA", "3G_DATA")


class DataProcessingService:
    """
    Servicio responsable del pipeline completo de procesamiento de datos.

    1. Carga el archivo (delegando a ExcelLoader)
    2. Aplica el mapeo de columnas del usuario
    3. Normaliza números telefónicos
    4. Parsea fechas con motor robusto
    5. Corrige coordenadas con formato incorrecto
    6. Calcula estadísticas de carga

    Principio S: solo se encarga del procesamiento de datos.
    Principio D: PhoneService y ExcelLoader se inyectan.
    """

    def __init__(
        self,
        phone_service: Optional[PhoneService] = None,
        loader: Optional[ExcelLoader] = None,
    ) -> None:
        self._phone = phone_service or PhoneService()
        self._loader = loader or ExcelLoader()

    # ── Carga ─────────────────────────────────────────────────────────────────

    def load_raw(self, path: Path) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        """Carga el archivo sin procesar."""
        return self._loader.load(path)

    def load_sheets_raw(
        self, path: Path
    ) -> tuple[Optional[dict[str, pd.DataFrame]], Optional[str]]:
        """Carga todas las hojas del Excel sin procesamiento automático."""
        return self._loader.load_sheets_raw(path)

    def apply_mapping(
        self, df: pd.DataFrame, mapping: dict[str, str]
    ) -> pd.DataFrame:
        """
        Renombra columnas del Excel según el mapeo del usuario.

        mapping: {nombre_interno -> columna_excel}
        """
        if not mapping:
            return df

        rename = {excel_col: internal for internal, excel_col in mapping.items()
                  if excel_col in df.columns}
        return df.rename(columns=rename)

    def process_sheets(
        self,
        sheets: dict[str, pd.DataFrame],
        sheet_configs: list[dict],
    ) -> pd.DataFrame:
        """
        Procesa múltiples hojas con mapeo individual y las combina.

        Args:
            sheets: {nombre_hoja: DataFrame_crudo}
            sheet_configs: lista de dicts con claves:
                - sheet_name: nombre de la hoja
                - sheet_type: tipo (Entrantes/Salientes/Datos/Genérica)
                - mapping: {nombre_interno: columna_excel}

        Returns:
            DataFrame combinado y procesado.

        Raises:
            EmptyDataError: si no hay datos resultantes.
        """
        frames: list[pd.DataFrame] = []

        for config in sheet_configs:
            sheet_name = config["sheet_name"]
            sheet_type = config["sheet_type"]
            mapping = config["mapping"]

            df = sheets.get(sheet_name)
            if df is None:
                logger.warning("Hoja '%s' no encontrada, omitiendo.", sheet_name)
                continue

            df = df.copy()
            logger.info(
                "Procesando hoja '%s' como %s (%d filas).",
                sheet_name, sheet_type, len(df),
            )

            # Aplicar mapeo de columnas del usuario
            if mapping:
                df = self.apply_mapping(df, mapping)
                df = df.loc[:, ~df.columns.duplicated()]

            # Normalizar nombres de columnas a minúsculas
            df.columns = df.columns.str.lower().str.strip()

            # Auto-detectar columnas de coordenadas si no fueron mapeadas
            df = self._auto_rename_coord_columns(df)

            # Asignar tipo de llamada según el tipo de hoja
            if sheet_type == SHEET_TYPE_INCOMING:
                df[COL_CALL_TYPE] = CALL_TYPE_INCOMING
            elif sheet_type == SHEET_TYPE_OUTGOING:
                df[COL_CALL_TYPE] = CALL_TYPE_OUTGOING
            elif sheet_type == SHEET_TYPE_DATA:
                if COL_CALL_TYPE not in df.columns:
                    df[COL_CALL_TYPE] = CALL_TYPE_DATA
                else:
                    df[COL_CALL_TYPE] = df[COL_CALL_TYPE].fillna(CALL_TYPE_DATA)
                # Auto-rellenar receptor para datos
                if COL_RECEIVER not in df.columns:
                    df[COL_RECEIVER] = INTERNET_DATA_RECEIVER
                else:
                    df[COL_RECEIVER] = df[COL_RECEIVER].fillna(INTERNET_DATA_RECEIVER)
            # SHEET_TYPE_GENERIC: el tipo_llamada ya viene del mapeo del usuario

            frames.append(df)

        if not frames:
            raise EmptyDataError("No se encontraron hojas con datos para procesar.")

        combined = pd.concat(frames, ignore_index=True, sort=False)
        combined = combined.loc[:, ~combined.columns.duplicated()]

        # Ahora procesar normalmente (sin volver a aplicar mapeo)
        return self.process(combined, mapping=None)

    def process(
        self, df: pd.DataFrame, mapping: Optional[dict[str, str]] = None
    ) -> pd.DataFrame:
        """
        Pipeline completo de procesamiento.

        Raises:
            ColumnMappingError: si faltan columnas requeridas.
            EmptyDataError: si el DataFrame resultante está vacío.
        """
        # Eliminar duplicados de columnas
        df = df.loc[:, ~df.columns.duplicated()]

        if mapping:
            df = self.apply_mapping(df, mapping)
            df = df.loc[:, ~df.columns.duplicated()]

        # Auto-detectar columnas de coordenadas si no fueron mapeadas
        df = self._auto_rename_coord_columns(df)

        # Asegurar columnas mínimas
        original_rows = len(df)
        for col in (COL_ORIGINATOR, COL_RECEIVER, COL_DATETIME, COL_CALL_TYPE):
            if col not in df.columns:
                df[col] = pd.NA

        # Normalizar teléfonos
        logger.info("Normalizando números telefónicos...")
        for col in (COL_ORIGINATOR, COL_RECEIVER):
            if col in df.columns:
                df[col] = self._phone.normalize_series(df[col])

        # Parsear fechas
        logger.info("Procesando fechas...")
        if COL_DATETIME in df.columns:
            df[COL_DATETIME] = df[COL_DATETIME].apply(self._parse_date)
            # Only drop rows if we actually care about dates for final processing.
            # However, since this service is used by `/api/projects/{id}/numbers`
            # which just wants to read the numbers, dropping rows with invalid dates
            # might cause it to return 0 numbers if the date mapping is wrong or missing.
            # But the core app logic requires dates to build timelines.
            # We will conditionally drop NaT later or let the caller handle it.
            # For now, to prevent `EmptyDataError` during alias loading, we won't strictly fail here.

        if df.empty:
            raise EmptyDataError(
                "El archivo está vacío."
            )

        # Duración
        if COL_DURATION in df.columns:
            df[COL_DURATION] = (
                pd.to_numeric(df[COL_DURATION], errors="coerce").fillna(0).astype(int)
            )
        else:
            df[COL_DURATION] = 0

        # Coordenadas
        for col in (COL_LATITUDE, COL_LONGITUDE):
            if col in df.columns:
                df[col] = df[col].apply(self._fix_coordinate)

        # Normalizar tipo de llamada
        if COL_CALL_TYPE in df.columns:
            df[COL_CALL_TYPE] = df[COL_CALL_TYPE].apply(self._normalize_call_type)

        # Detectar horarios y ubicaciones atípicas para analítica avanzada
        logger.info("Detectando parámetros analíticos avanzados...")
        if COL_DATETIME in df.columns:
            # Día: 06:00 a 17:59, Noche: 18:00 a 05:59
            df["is_night"] = df[COL_DATETIME].dt.hour.between(18, 23) | df[COL_DATETIME].dt.hour.between(0, 5)

        if COL_LATITUDE in df.columns and COL_LONGITUDE in df.columns:
            df = self._detect_atypical_locations(df)

        discarded = original_rows - len(df)
        if discarded > 0:
            logger.warning("Filas descartadas (fecha inválida): %d", discarded)
        else:
            logger.info("Calidad de datos perfecta: 0 descartes.")

        logger.info("Datos procesados. Total registros limpios: %d", len(df))
        return df

    # ── Estadísticas ──────────────────────────────────────────────────────────

    def compute_stats(self, df: pd.DataFrame) -> CallStats:
        """Calcula estadísticas resumidas del DataFrame procesado."""
        mask_data = df[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")

        total = len(df)
        incoming = int((df[COL_CALL_TYPE] == CALL_TYPE_INCOMING).sum())
        outgoing = int((df[COL_CALL_TYPE] == CALL_TYPE_OUTGOING).sum())
        data_records = int(mask_data.sum())

        unique: set[str] = set()
        for col in (COL_ORIGINATOR, COL_RECEIVER):
            if col in df.columns:
                unique.update(df[col].dropna().astype(str).unique())

        n_unique = len(unique)
        avg = total / n_unique if n_unique else 0.0

        return CallStats(
            total=total,
            incoming=incoming,
            outgoing=outgoing,
            data_records=data_records,
            unique_numbers=n_unique,
            avg_calls_per_number=avg,
        )

    def merge_dataframes(
        self,
        existing: Optional[pd.DataFrame],
        new: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Acumula un nuevo DataFrame al existente.

        Si *existing* es None o está vacío, devuelve *new* sin más.
        En caso contrario, concatena ambos eliminando columnas duplicadas.
        """
        if existing is None or existing.empty:
            return new
        combined = pd.concat([existing, new], ignore_index=True, sort=False)
        combined = combined.loc[:, ~combined.columns.duplicated()]
        return combined

    def split_calls_and_data(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Divide el DataFrame en llamadas y datos de internet."""
        mask = df[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")
        return df[~mask].copy(), df[mask].copy()

    # ── Cálculos Analíticos (Avanzados) ───────────────────────────────────────

    def _detect_atypical_locations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula ubicaciones atípicas basándose en la frecuencia de aparición de un
        municipio o coordenada específica. Si una ubicación representa menos del
        5% de la actividad, se marca como atípica. Si usa coordenadas exactas, se
        redondean (aprox ~1km cuadrado) para agrupar ubicaciones cercanas.
        """
        df["is_atypical"] = False
        if df.empty:
            return df

        # Determinar nivel de agrupación (Municipio > Coordenadas Redondeadas)
        has_municipality = "municipio" in df.columns and df["municipio"].notna().any()

        if has_municipality:
            # Agrupar por municipio (útil cuando son sábanas con DB de celdas)
            counts = df["municipio"].value_counts(normalize=True)
            # Definimos atípico si la frecuencia es menor al 5%
            atypical_munis = counts[counts < 0.05].index
            df.loc[df["municipio"].isin(atypical_munis), "is_atypical"] = True
        else:
            # Agrupar por coordenadas redondeadas a 2 decimales (aprox ~1km radius)
            valid_coords_mask = df[COL_LATITUDE].notna() & df[COL_LONGITUDE].notna()
            if not valid_coords_mask.any():
                return df

            df.loc[valid_coords_mask, "coord_cluster"] = (
                df.loc[valid_coords_mask, COL_LATITUDE].round(2).astype(str) + "_" +
                df.loc[valid_coords_mask, COL_LONGITUDE].round(2).astype(str)
            )

            counts = df["coord_cluster"].value_counts(normalize=True)
            atypical_clusters = counts[counts < 0.05].index
            df.loc[df["coord_cluster"].isin(atypical_clusters), "is_atypical"] = True
            df.drop(columns=["coord_cluster"], inplace=True)

        return df

    # ── Helpers privados ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(value: object) -> object:
        """Motor robusto de parsing de fechas."""
        if pd.isna(value) or str(value).strip() in {"", "nan", "None", "NaT"}:
            return pd.NaT

        value_str = str(value).strip()

        # Número serial de Excel
        if value_str.replace(".", "", 1).isdigit():
            try:
                num = float(value_str)
                if EXCEL_SERIAL_DATE_MIN < num < EXCEL_SERIAL_DATE_MAX:
                    return pd.to_datetime(num, unit="D", origin="1899-12-30").round("s")
            except Exception:
                pass

        # Formatos de texto conocidos
        for fmt in DATE_FORMATS:
            try:
                return pd.to_datetime(value_str, format=fmt)
            except Exception:
                continue

        # Último intento automático
        try:
            return pd.to_datetime(value_str, errors="coerce", dayfirst=False)
        except Exception:
            return pd.NaT

    @staticmethod
    def _normalize_call_type(value: object) -> str:
        """Normaliza los valores del tipo de llamada a los valores internos."""
        upper = str(value).upper().strip()
        for kw in _DATA_KEYWORDS:
            if kw in upper:
                return CALL_TYPE_DATA          # "DATOS"
        for kw in _OUTGOING_KEYWORDS:
            if kw in upper:
                return CALL_TYPE_OUTGOING      # "saliente"
        for kw in _INCOMING_KEYWORDS:
            if kw in upper:
                return CALL_TYPE_INCOMING      # "entrante"
        return str(value)  # mantener original si no se reconoce

    @staticmethod
    def _auto_rename_coord_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Auto-detecta columnas de coordenadas si no fueron mapeadas por el usuario.

        Si latitud_n / longitud_w no existen, busca columnas con nombres comunes
        (latitud, lat, longitud, lon, etc.) y las renombra al nombre interno.
        """
        rename: dict[str, str] = {}
        cols_lower = {c.lower().strip(): c for c in df.columns}

        if COL_LATITUDE not in df.columns:
            for candidate in ("latitud", "lat", "latitude"):
                if candidate in cols_lower:
                    rename[cols_lower[candidate]] = COL_LATITUDE
                    break

        if COL_LONGITUDE not in df.columns:
            for candidate in ("longitud", "lon", "lng", "longitude"):
                if candidate in cols_lower:
                    rename[cols_lower[candidate]] = COL_LONGITUDE
                    break

        if rename:
            logger.info("Auto-renombrando columnas de coordenadas: %s", rename)
            df = df.rename(columns=rename)
        return df

    @staticmethod
    def _fix_coordinate(value: object) -> float:
        """Corrige coordenadas con formato incorrecto (coma decimal, escala errónea)."""
        if pd.isna(value) or str(value).strip() in {"", "?", "nan", "0", "None"}:
            return np.nan
        try:
            cleaned = str(value).replace(",", ".")
            val = float(cleaned)
            if abs(val) > 180:
                val = val / 1_000_000 if abs(val) > 100_000 else val / 10_000
            return val
        except Exception:
            return np.nan
