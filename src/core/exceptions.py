"""
Excepciones personalizadas de la aplicación.

Jerarquía de excepciones claras para un manejo de errores explícito
y sin depender de excepciones genéricas de Python.
"""
from __future__ import annotations


class AppError(Exception):
    """Excepción base de la aplicación."""


# ── Carga de datos ────────────────────────────────────────────────────────────

class DataLoadError(AppError):
    """Error al cargar un archivo de datos."""


class UnsupportedFileFormatError(DataLoadError):
    """Formato de archivo no soportado."""


class EmptyDataError(DataLoadError):
    """El archivo no contiene datos válidos tras la limpieza."""


class ColumnMappingError(DataLoadError):
    """El mapeo de columnas es inválido o incompleto."""


# ── Geocodificación ───────────────────────────────────────────────────────────

class GeocodingError(AppError):
    """Error general en el proceso de geocodificación."""


class DatabaseNotFoundError(GeocodingError):
    """La base de datos de celdas o municipios no se encontró."""


# ── Generación de informes ────────────────────────────────────────────────────

class ReportGenerationError(AppError):
    """Error al generar el informe HTML."""


class TemplateRenderError(ReportGenerationError):
    """Error al renderizar la plantilla Jinja2."""


class MapGenerationError(ReportGenerationError):
    """Error al generar un mapa."""


class ChartGenerationError(ReportGenerationError):
    """Error al generar una gráfica."""


# ── Carga remota ─────────────────────────────────────────────────────────────

class UploadError(AppError):
    """Error al subir archivos al servidor remoto."""


class FtpConnectionError(UploadError):
    """No se pudo establecer la conexión FTP."""


class FtpCredentialsError(UploadError):
    """Credenciales FTP no configuradas o inválidas."""


# ── Configuración ─────────────────────────────────────────────────────────────

class ConfigurationError(AppError):
    """Error de configuración de la aplicación."""
