import pytest
import sys
from unittest.mock import MagicMock

# Mocking pandas and other dependencies that are missing in the environment
sys.modules['pandas'] = MagicMock()
sys.modules['geo_utils'] = MagicMock()
sys.modules['colombia_data'] = MagicMock()
sys.modules['jinja2'] = MagicMock()

from src.report_generator import obtener_nombre_mostrado

def test_obtener_nombre_mostrado_con_alias():
    """Test when the number has an assigned name."""
    nombres_asignados = {"123456789": "Juan Perez"}
    assert obtener_nombre_mostrado("123456789", nombres_asignados) == "123456789 (Juan Perez)"

def test_obtener_nombre_mostrado_sin_alias():
    """Test when the number does not have an assigned name."""
    nombres_asignados = {"123456789": "Juan Perez"}
    assert obtener_nombre_mostrado("987654321", nombres_asignados) == "987654321"

def test_obtener_nombre_mostrado_nombres_asignados_none():
    """Test when the dictionary of assigned names is None."""
    assert obtener_nombre_mostrado("123456789", None) == "123456789"

def test_obtener_nombre_mostrado_nombres_asignados_vacio():
    """Test when the dictionary of assigned names is empty."""
    assert obtener_nombre_mostrado("123456789", {}) == "123456789"

def test_obtener_nombre_mostrado_tipo_int():
    """Test when the number is passed as an integer."""
    nombres_asignados = {"123": "Test"}
    assert obtener_nombre_mostrado(123, nombres_asignados) == "123 (Test)"

def test_obtener_nombre_mostrado_con_espacios():
    """Test when the number string has surrounding whitespace."""
    nombres_asignados = {"123": "Test"}
    assert obtener_nombre_mostrado(" 123 ", nombres_asignados) == "123 (Test)"

def test_obtener_nombre_mostrado_unassigned_name():
    """Specific test for unassigned name based on the task rationale."""
    nombres_asignados = {"5551234": "Alice"}
    # A number not in the dictionary should return just the number
    assert obtener_nombre_mostrado("9998887", nombres_asignados) == "9998887"
