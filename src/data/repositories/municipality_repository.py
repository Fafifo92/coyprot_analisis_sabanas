"""
Repositorio de municipios de Colombia.

Provee búsqueda por nombre (tolerante a tildes) y por proximidad
geográfica usando la fórmula de Haversine.
"""
from __future__ import annotations

import logging
import math
import unicodedata
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from config.constants import MIN_MUNICIPALITY_NAME_LEN, UNKNOWN_LOCATION
from config.settings import settings
from core.exceptions import DatabaseNotFoundError

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Elimina tildes y pasa a mayúsculas para comparación insensible."""
    if not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize("NFD", text)
    without_accents = "".join(
        c for c in normalized if unicodedata.category(c) != "Mn"
    )
    return without_accents.upper().strip()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos puntos usando la fórmula de Haversine."""
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MunicipalityRepository:
    """
    Repositorio de municipios colombianos con búsqueda geoespacial.

    Implementa IMunicipalityRepository.
    Utiliza un índice normalizado (sin tildes) para búsquedas rápidas por nombre.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or settings.municipalities_db_path
        self._df: pd.DataFrame = pd.DataFrame()
        self._load()

    # ── Carga ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._db_path.exists():
            raise DatabaseNotFoundError(
                f"Base de datos de municipios no encontrada: {self._db_path}"
            )
        try:
            self._df = pd.read_csv(
                self._db_path, sep=";", encoding="utf-8-sig"
            )
            self._df["muni_norm"] = self._df["Municipio"].apply(_normalize_text)
            self._df["depto_norm"] = self._df["Departamento"].apply(_normalize_text)
            logger.info(
                "Base de datos geográfica cargada: %d municipios.", len(self._df)
            )
        except Exception as exc:
            logger.error("Error cargando municipios_colombia.csv: %s", exc)
            self._df = pd.DataFrame()

    # ── Consulta ──────────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return not self._df.empty

    def find_nearest(self, lat: float, lon: float) -> tuple[str, str]:
        """
        Encuentra (departamento, municipio) del punto más cercano.

        Optimización: primero filtra en un cuadro bounding-box de ~1°
        antes de calcular distancias exactas.
        """
        if not self.is_available or not isinstance(lat, (int, float)):
            return UNKNOWN_LOCATION, UNKNOWN_LOCATION

        bbox = self._df[
            (self._df["Latitud"].between(lat - 1, lat + 1))
            & (self._df["Longitud"].between(lon - 1, lon + 1))
        ]
        search = bbox if not bbox.empty else self._df
        if search.empty:
            return UNKNOWN_LOCATION, UNKNOWN_LOCATION

        # Vectorized Haversine calculation for performance boost
        lats2 = np.radians(search["Latitud"].values)
        lons2 = np.radians(search["Longitud"].values)
        lat1_rad = math.radians(lat)
        lon1_rad = math.radians(lon)

        dlat = lats2 - lat1_rad
        dlon = lons2 - lon1_rad

        a = (
            np.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * np.cos(lats2) * np.sin(dlon / 2) ** 2
        )
        # Handle potential invalid values (though rare in this dataset)
        a = np.clip(a, 0, 1)
        distances = 6371.0 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        # Find the index of the minimum distance (ignoring NaNs if present)
        idx_min = np.nanargmin(distances)
        best_row = search.iloc[idx_min]

        return str(best_row["Departamento"]), str(best_row["Municipio"])

    def find_by_name(self, name: str) -> Optional[tuple[str, float, float]]:
        """
        Busca un municipio cuyo nombre aparezca dentro del texto dado.

        Evita falsos positivos con nombres cortos (< MIN_MUNICIPALITY_NAME_LEN).

        Returns:
            Tupla (nombre_oficial, latitud, longitud) o None.
        """
        if not self.is_available or not name:
            return None

        text_norm = _normalize_text(str(name))

        for row in self._df.itertuples(index=False):
            muni_norm: str = row.muni_norm
            if len(muni_norm) < MIN_MUNICIPALITY_NAME_LEN:
                continue
            if muni_norm in text_norm:
                return row.Municipio, float(row.Latitud), float(row.Longitud)

        return None
