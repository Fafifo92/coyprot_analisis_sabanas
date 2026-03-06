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
            df.dropna(subset=[COL_DATETIME], inplace=True)

        if df.empty:
            raise EmptyDataError(
                "Todas las fechas fueron inválidas o el archivo está vacío."
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

    def split_calls_and_data(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Divide el DataFrame en llamadas y datos de internet."""
        mask = df[COL_CALL_TYPE].astype(str).str.upper().str.contains("DATO")
        return df[~mask].copy(), df[mask].copy()

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
