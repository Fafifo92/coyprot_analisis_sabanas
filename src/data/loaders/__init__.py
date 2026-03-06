"""
Cargadores de archivos de datos.

Implementan el patrón Strategy: cada cargador maneja un formato diferente
y todos exponen la misma interfaz IDataLoader.
"""
from .excel_loader import ExcelLoader

__all__ = ["ExcelLoader"]
