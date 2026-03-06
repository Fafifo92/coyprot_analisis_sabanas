"""
Repositorio de torres celulares (antenas BTS).

Lee la base de datos de celdas.csv y provee búsqueda por nombre de sitio,
agrupando múltiples sectores de la misma torre física.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from config.constants import CELL_TECH_SUFFIXES_PATTERN, COL_LATITUDE, COL_LONGITUDE
from core.exceptions import DatabaseNotFoundError

logger = logging.getLogger(__name__)


class CellTowerRepository:
    """
    Repositorio para consulta de coordenadas de torres celulares.

    Implementa ICellTowerRepository.
    Agrupa sectores de la misma torre y promedia sus coordenadas,
    mejorando la precisión de la geolocalización.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._sites: pd.DataFrame = pd.DataFrame()
        self._load()

    # ── Carga ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._db_path.exists():
            raise DatabaseNotFoundError(
                f"Base de datos de celdas no encontrada: {self._db_path}"
            )

        raw = self._read_csv()
        if raw is None or raw.empty:
            logger.warning("La base de datos de celdas está vacía o es ilegible.")
            return

        raw.columns = [c.strip() for c in raw.columns]

        col_name = self._detect_column(raw, ("BTS", "Nombre", "Cell"))
        col_lat = self._detect_column(raw, ("Latitud", "LAT"))
        col_lon = self._detect_column(raw, ("Longitud", "LON"))

        if not all([col_name, col_lat, col_lon]):
            logger.error(
                "No se detectaron columnas BTS/Lat/Lon en celdas.csv. "
                "Columnas disponibles: %s",
                raw.columns.tolist(),
            )
            return

        df = raw.rename(columns={col_name: "raw_name", col_lat: "lat", col_lon: "lon"})
        df = self._clean_coordinates(df)
        df["site_root"] = df["raw_name"].apply(self._clean_site_name)
        self._sites = (
            df.groupby("site_root")[["lat", "lon"]].mean().reset_index()
        )
        logger.info("Base de celdas indexada: %d sitios únicos.", len(self._sites))

    def _read_csv(self) -> Optional[pd.DataFrame]:
        """Intenta leer el CSV con distintos separadores."""
        for sep in (";", ","):
            try:
                df = pd.read_csv(
                    self._db_path,
                    sep=sep,
                    encoding="latin-1",
                    on_bad_lines="skip",
                    engine="python",
                )
                if not df.empty:
                    return df
            except Exception as exc:
                logger.debug("Error leyendo con sep='%s': %s", sep, exc)
        return None

    @staticmethod
    def _detect_column(df: pd.DataFrame, keywords: tuple[str, ...]) -> Optional[str]:
        for col in df.columns:
            if any(kw.upper() in col.upper() for kw in keywords):
                return col
        return None

    @staticmethod
    def _clean_coordinates(df: pd.DataFrame) -> pd.DataFrame:
        for col in ("lat", "lon"):
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna(subset=["lat", "lon"])

    @staticmethod
    def _clean_site_name(name: str) -> str:
        """Elimina sufijos técnicos para obtener el nombre raíz del sitio."""
        if pd.isna(name):
            return ""
        cleaned = str(name).upper().strip()
        # Ejecutar dos veces para sufijos anidados (ej: _LTE_R1)
        for _ in range(2):
            cleaned = re.sub(CELL_TECH_SUFFIXES_PATTERN, "", cleaned)
        return cleaned

    # ── Consulta ──────────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return not self._sites.empty

    def find_by_name(self, site_root: str) -> Optional[tuple[float, float]]:
        """Busca coordenadas de una antena por nombre raíz."""
        if not self.is_available:
            return None
        cleaned = self._clean_site_name(site_root)
        match = self._sites[self._sites["site_root"] == cleaned]
        if match.empty:
            return None
        row = match.iloc[0]
        return float(row["lat"]), float(row["lon"])

    def bulk_lookup(self, df: pd.DataFrame, cell_name_col: str) -> pd.DataFrame:
        """
        Enriquece el DataFrame con coordenadas usando un LEFT JOIN vectorizado.

        Es mucho más eficiente que iterar fila por fila.
        """
        if not self.is_available or cell_name_col not in df.columns:
            return df

        df = df.copy()
        df["_site_root"] = df[cell_name_col].apply(self._clean_site_name)

        merged = df.merge(
            self._sites,
            left_on="_site_root",
            right_on="site_root",
            how="left",
        )

        # Rellenar coordenadas solo donde faltan
        if COL_LATITUDE not in merged.columns:
            merged[COL_LATITUDE] = merged["lat"]
        else:
            merged[COL_LATITUDE] = merged[COL_LATITUDE].fillna(merged["lat"])

        if COL_LONGITUDE not in merged.columns:
            merged[COL_LONGITUDE] = merged["lon"]
        else:
            merged[COL_LONGITUDE] = merged[COL_LONGITUDE].fillna(merged["lon"])

        drop_cols = [c for c in ("_site_root", "site_root", "lat", "lon") if c in merged]
        merged.drop(columns=drop_cols, inplace=True)

        found = merged[COL_LATITUDE].notna().sum()
        logger.info("Geocodificación por celdas: %d registros ubicados.", found)
        return merged
