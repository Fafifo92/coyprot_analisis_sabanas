"""
Repositorios de datos.

Encapsulan el acceso a las bases de datos de celdas y municipios,
siguiendo el patrón Repository para desacoplar la lógica de negocio
del acceso a datos.
"""
from .cell_tower_repository import CellTowerRepository
from .municipality_repository import MunicipalityRepository

__all__ = ["CellTowerRepository", "MunicipalityRepository"]
