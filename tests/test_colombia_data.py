import unittest
from unittest.mock import MagicMock
import sys

# Mock pandas before importing colombia_data
sys.modules["pandas"] = MagicMock()

from colombia_data import normalizar_texto

class TestColombiaData(unittest.TestCase):
    def test_normalizar_texto_happy_path(self):
        self.assertEqual(normalizar_texto("BOGOTÁ"), "BOGOTA")
        self.assertEqual(normalizar_texto("Medellín"), "MEDELLIN")
        self.assertEqual(normalizar_texto("Cali"), "CALI")

    def test_normalizar_texto_whitespace(self):
        self.assertEqual(normalizar_texto("  Medellín  "), "MEDELLIN")
        self.assertEqual(normalizar_texto("\nBOGOTÁ\t"), "BOGOTA")

    def test_normalizar_texto_empty_string(self):
        self.assertEqual(normalizar_texto(""), "")

    def test_normalizar_texto_non_string_inputs(self):
        self.assertEqual(normalizar_texto(None), "")
        self.assertEqual(normalizar_texto(123), "")
        self.assertEqual(normalizar_texto([]), "")
        self.assertEqual(normalizar_texto({}), "")

    def test_normalizar_texto_special_characters(self):
        self.assertEqual(normalizar_texto("San Andrés!"), "SAN ANDRES!")
        self.assertEqual(normalizar_texto("¿Qué?"), "¿QUE?")
        self.assertEqual(normalizar_texto("123-ABC"), "123-ABC")

if __name__ == "__main__":
    unittest.main()
