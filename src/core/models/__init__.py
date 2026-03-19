"""
Modelos de dominio de la aplicación.

Dataclasses inmutables que representan las entidades del negocio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class RouteMapMode(str, Enum):
    """Modo de generación de mapas de ruta para PDF."""

    DAILY = "daily"
    CONSOLIDATED = "consolidated"


@dataclass
class PdfExportConfig:
    """Configuración específica para la exportación PDF."""

    route_map_mode: RouteMapMode = RouteMapMode.CONSOLIDATED
    include_route_maps: bool = True
    include_location_maps: bool = True
    ftp_url: str = ""


@dataclass(frozen=True)
class GeographicInfo:
    """Información geográfica de un punto."""

    department: str = "Desconocido"
    municipality: str = "Desconocido"
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def coords_str(self) -> str:
        if self.has_coordinates:
            return f"{self.latitude}, {self.longitude}"
        return "N/A"


@dataclass(frozen=True)
class PdfAttachment:
    """Adjunto PDF de un informe."""

    category: str
    source_path: Path

    @property
    def filename(self) -> str:
        return self.source_path.name

    @property
    def is_valid(self) -> bool:
        return self.source_path.exists() and self.source_path.suffix.lower() == ".pdf"


@dataclass
class CaseMetadata:
    """Metadatos del caso de análisis."""

    fields: dict[str, str] = field(default_factory=dict)

    @classmethod
    def with_defaults(cls) -> "CaseMetadata":
        from config.constants import DEFAULT_CASE_FIELDS
        return cls(fields={k: "" for k in DEFAULT_CASE_FIELDS})

    def to_dict(self) -> dict[str, str]:
        return dict(self.fields)


@dataclass(frozen=True)
class CallStats:
    """Estadísticas resumidas de llamadas."""

    total: int
    incoming: int
    outgoing: int
    data_records: int
    unique_numbers: int
    avg_calls_per_number: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "total": self.total,
            "entrantes": self.incoming,
            "salientes": self.outgoing,
            "datos": self.data_records,
            "numeros_unicos": self.unique_numbers,
            "promedio": round(self.avg_calls_per_number, 2),
        }


@dataclass
class ReportConfig:
    """Configuración completa para generar un informe."""

    report_name: str
    include_letterhead: bool = True
    upload_ftp: bool = False
    aliases: dict[str, str] = field(default_factory=dict)
    case_metadata: CaseMetadata = field(default_factory=CaseMetadata.with_defaults)
    pdf_attachments: list[PdfAttachment] = field(default_factory=list)

    @property
    def safe_name(self) -> str:
        """Nombre de carpeta sanitizado (sin espacios)."""
        return self.report_name.strip().replace(" ", "_") or "Informe_Llamadas"

    def get_alias(self, number: str) -> str | None:
        return self.aliases.get(str(number).strip())

    def display_name(self, number: str) -> str:
        """Devuelve 'número (alias)' o solo el número."""
        alias = self.get_alias(number)
        num = str(number).strip()
        return f"{num} ({alias})" if alias else num


@dataclass(frozen=True)
class LoadResult:
    """Resultado de una operación de carga de datos."""

    success: bool
    stats: Optional[CallStats] = None
    error_message: Optional[str] = None

    @classmethod
    def ok(cls, stats: CallStats) -> "LoadResult":
        return cls(success=True, stats=stats)

    @classmethod
    def fail(cls, message: str) -> "LoadResult":
        return cls(success=False, error_message=message)
