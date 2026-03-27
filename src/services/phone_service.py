"""
Servicio de normalización de números telefónicos colombianos.

Centraliza toda la lógica de limpieza y validación de teléfonos.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import phonenumbers
import pandas as pd

from config.constants import UNKNOWN_NUMBER

logger = logging.getLogger(__name__)


class PhoneService:
    """
    Servicio de normalización de números de teléfono colombianos.

    Convierte cualquier representación de un número al formato
    de 10 dígitos estándar de Colombia o devuelve 'Desconocido'.

    Principio S (Single Responsibility): solo limpia números.
    """

    COUNTRY_CODE = "57"
    REGION = "CO"

    def normalize(self, raw: object) -> str:
        """
        Limpia y estandariza un número telefónico colombiano.

        Maneja:
        - Valores nulos o de Excel
        - Números con puntos, comas, espacios, guiones
        - Prefijos internacionales (+57, 0057, 009573...)
        - Números ya correctos de 10 dígitos
        """
        if pd.isna(raw) or str(raw).strip() in {
            "", "nan", "None", UNKNOWN_NUMBER, "?", "0"
        }:
            return UNKNOWN_NUMBER

        # Extraer solo dígitos
        digits = re.sub(r"\D", "", str(raw))
        length = len(digits)

        if length == 10:
            return digits

        if length == 12 and digits.startswith(self.COUNTRY_CODE):
            return digits[2:]

        if length > 10:
            last_10 = digits[-10:]
            if last_10.startswith("3") or last_10.startswith("60"):
                return last_10
            # Buscar prefijo 57
            if self.COUNTRY_CODE in digits:
                _, _, rest = digits.partition(self.COUNTRY_CODE)
                candidate = rest[:10]
                if len(candidate) == 10 and (
                    candidate.startswith("3") or candidate.startswith("60")
                ):
                    return candidate

        return digits if digits else UNKNOWN_NUMBER

    def normalize_series(self, series: pd.Series) -> pd.Series:
        """Aplica normalización a toda una Serie de pandas de forma vectorizada."""
        return series.apply(self.normalize)

    def validate(self, number: str) -> bool:
        """Valida si el número es posible según la librería phonenumbers."""
        try:
            parsed = phonenumbers.parse(
                number if number.startswith("+") else number,
                self.REGION if not number.startswith("+") else None,
            )
            return phonenumbers.is_valid_number(parsed)
        except Exception:
            return False

    def format_international(self, number: str) -> str:
        """Retorna el número en formato internacional legible (+57 300 123 4567)."""
        try:
            parsed = phonenumbers.parse(
                number if number.startswith("+") else number,
                self.REGION if not number.startswith("+") else None,
            )
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
        except Exception:
            pass
        return number

    def detect_region(self, number: str) -> Optional[str]:
        """Detecta el código de país ISO del número."""
        try:
            parsed = phonenumbers.parse(number, None)
            return phonenumbers.region_code_for_number(parsed)
        except Exception:
            return None
