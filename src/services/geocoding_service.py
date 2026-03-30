"""
Servicio de geocodificación.

Orquesta múltiples estrategias de geocodificación en cascada:
1. Base de datos de torres celulares (preciso)
2. Inferencia por nombre de municipio en el nombre de la antena (aprox.)

Implementa el patrón Strategy para las geocodificaciones
y el patrón Chain of Responsibility para la cascada.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config.constants import COL_CELL_NAME, COL_LATITUDE, COL_LONGITUDE
from data.repositories.cell_tower_repository import CellTowerRepository
from data.repositories.municipality_repository import MunicipalityRepository

logger = logging.getLogger(__name__)


class GeocodingService:
    """
    Orquesta la geocodificación de registros de llamadas.

    Aplica las estrategias en cascada:
    1. CellTowerRepository.bulk_lookup (merge vectorizado con DB celdas)
    2. MunicipalityRepository.find_by_name (inferencia por nombre de antena)

    Principio D: recibe los repositorios por inyección de dependencias.
    """

    def __init__(
        self,
        cell_repo: Optional[CellTowerRepository] = None,
        muni_repo: Optional[MunicipalityRepository] = None,
    ) -> None:
        self._cell_repo = cell_repo
        self._muni_repo = muni_repo

    # ── Estrategia 1: DB de celdas ────────────────────────────────────────────

    def geocode_by_cell_db(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Llena coordenadas faltantes usando la base de datos de torres celulares.
        Solo actúa si no hay coordenadas GPS nativas y existe nombre_celda.
        """
        if self._cell_repo is None or not self._cell_repo.is_available:
            logger.debug("Repositorio de celdas no disponible.")
            return df

        if COL_CELL_NAME not in df.columns:
            return df

        has_native_coords = (
            COL_LATITUDE in df.columns and df[COL_LATITUDE].notna().any()
        )
        if has_native_coords:
            logger.debug("Coordenadas GPS nativas detectadas. Omitiendo DB celdas.")
            return df

        logger.info("Geolocalizando con base de datos de celdas...")
        return self._cell_repo.bulk_lookup(df, COL_CELL_NAME)

    # ── Estrategia 2: Inferencia por municipio ────────────────────────────────

    def geocode_by_municipality_name(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Infiere coordenadas buscando el nombre del municipio en el nombre de la antena.
        Solo aplica a filas sin coordenadas.
        """
        if self._muni_repo is None or not self._muni_repo.is_available:
            return df

        if COL_CELL_NAME not in df.columns:
            return df

        for col in (COL_LATITUDE, COL_LONGITUDE):
            if col not in df.columns:
                df[col] = pd.NA

        count = 0
        for row in df.itertuples():
            idx = row.Index
            if pd.notna(getattr(row, COL_LATITUDE, None)) and pd.notna(getattr(row, COL_LONGITUDE, None)):
                continue
            cell_name = getattr(row, COL_CELL_NAME, None)
            result = self._muni_repo.find_by_name(str(cell_name) if cell_name else "")
            if result:
                _, lat, lon = result
                df.at[idx, COL_LATITUDE] = lat
                df.at[idx, COL_LONGITUDE] = lon
                count += 1

        logger.info("Inferencia por municipio: %d registros recuperados.", count)
        return df

    # ── Cobertura completa ────────────────────────────────────────────────────

    def count_missing_coords(self, df: pd.DataFrame) -> int:
        if COL_LATITUDE not in df.columns:
            return len(df)
        return int(df[COL_LATITUDE].isna().sum())

    def get_location(self, lat: float, lon: float) -> tuple[str, str]:
        """Devuelve (departamento, municipio) para unas coordenadas dadas."""
        if self._muni_repo is None:
            return "Desconocido", "Desconocido"
        return self._muni_repo.find_nearest(lat, lon)

    @classmethod
    def from_paths(
        cls,
        cell_db_path: Optional[Path] = None,
        muni_db_path: Optional[Path] = None,
    ) -> "GeocodingService":
        """
        Factory method para construir el servicio desde rutas de archivo.
        Captura errores de DB sin propagar para que la app funcione parcialmente.
        """
        cell_repo: Optional[CellTowerRepository] = None
        muni_repo: Optional[MunicipalityRepository] = None

        if cell_db_path and cell_db_path.exists():
            try:
                cell_repo = CellTowerRepository(cell_db_path)
            except Exception as exc:
                logger.warning("No se pudo cargar DB celdas: %s", exc)

        if muni_db_path and muni_db_path.exists():
            try:
                muni_repo = MunicipalityRepository(muni_db_path)
            except Exception as exc:
                logger.warning("No se pudo cargar DB municipios: %s", exc)

        return cls(cell_repo=cell_repo, muni_repo=muni_repo)
