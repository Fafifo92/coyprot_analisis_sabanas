from dataclasses import dataclass
from datetime import datetime
import math

@dataclass
class Llamada:
    """
    Modelo de datos para representar una llamada.
    """
    originador: str
    receptor: str
    duracion: int
    fecha_hora: datetime
    latitud_n: float = None
    longitud_w: float = None
    
    def __post_init__(self):
        """Convierte la fecha y la duración en los formatos correctos."""
        if isinstance(self.fecha_hora, str):
            try:
                self.fecha_hora = datetime.strptime(self.fecha_hora, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.fecha_hora = None
        
        try:
            self.duracion = int(self.duracion)
        except ValueError:
            self.duracion = 0

        # Validar coordenadas
        self.latitud_n = self.validar_coordenada(self.latitud_n)
        self.longitud_w = self.validar_coordenada(self.longitud_w)

    def validar_coordenada(self, valor):
        """Corrige y valida coordenadas geográficas."""
        if valor is None or math.isnan(valor):
            return None
        try:
            valor = float(valor)
            if abs(valor) > 180:  # Error típico de formato
                valor /= 10000
            return valor
        except ValueError:
            return None

@dataclass
class ResumenLlamadas:
    """
    Modelo de datos para representar estadísticas generales de llamadas.
    """
    total_llamadas: int
    total_numeros: int
    promedio_llamadas: float
