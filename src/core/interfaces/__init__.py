"""
Interfaces (Protocols) del dominio central.

Define los contratos que deben cumplir las implementaciones concretas.
Esto permite el principio D (Dependency Inversion) de SOLID:
los módulos de alto nivel dependen de abstracciones, no de implementaciones.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class IGeocoderStrategy(Protocol):
    """
    Estrategia de geocodificación.

    Cualquier implementación debe registrar coordenadas
    en un DataFrame a partir de los datos disponibles.
    """

    def geocode(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Intenta enriquecer el DataFrame con coordenadas geográficas.

        Returns:
            DataFrame con columnas 'latitud_n' y 'longitud_w' completadas
            donde fue posible. Las filas sin coordenadas mantienen NaN.
        """
        ...


@runtime_checkable
class ICellTowerRepository(Protocol):
    """Repositorio de antenas celulares."""

    def find_by_name(self, site_root: str) -> tuple[float, float] | None:
        """
        Busca coordenadas de una antena por su nombre raíz.

        Returns:
            Tupla (latitud, longitud) o None si no se encontró.
        """
        ...

    def bulk_lookup(self, df: pd.DataFrame, cell_name_col: str) -> pd.DataFrame:
        """
        Realiza una búsqueda masiva de coordenadas para un DataFrame.

        Returns:
            DataFrame enriquecido con columnas de coordenadas.
        """
        ...


@runtime_checkable
class IMunicipalityRepository(Protocol):
    """Repositorio de municipios de Colombia."""

    def find_nearest(self, lat: float, lon: float) -> tuple[str, str]:
        """
        Encuentra el municipio más cercano a las coordenadas dadas.

        Returns:
            Tupla (departamento, municipio).
        """
        ...

    def find_by_name(self, name: str) -> tuple[str, float, float] | None:
        """
        Busca un municipio por nombre (tolerante a tildes).

        Returns:
            Tupla (nombre_oficial, latitud, longitud) o None.
        """
        ...


@runtime_checkable
class IDataLoader(Protocol):
    """Cargador de datos de llamadas."""

    def can_load(self, path: Path) -> bool:
        """Indica si este cargador puede manejar el archivo dado."""
        ...

    def load(self, path: Path) -> tuple[pd.DataFrame | None, str | None]:
        """
        Carga el archivo y devuelve el DataFrame crudo.

        Returns:
            Tupla (dataframe, error). Si error es None, la carga fue exitosa.
        """
        ...


@runtime_checkable
class IReportBuilder(Protocol):
    """Constructor de artefactos del reporte (mapas, gráficas)."""

    def build(self, df: pd.DataFrame, output_path: Path, **kwargs: object) -> None:
        """
        Genera un artefacto de reporte y lo guarda en output_path.

        Args:
            df: DataFrame con los datos de llamadas.
            output_path: Ruta donde guardar el artefacto generado.
            **kwargs: Parámetros adicionales específicos del builder.
        """
        ...
