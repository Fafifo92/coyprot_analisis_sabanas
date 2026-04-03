import unittest
from unittest.mock import MagicMock, patch
import io
import sys

# Mock tkinter before importing utils since it's not available in the environment
mock_tk = MagicMock()
sys.modules["tkinter"] = mock_tk

from utils import manejar_excepcion

def test_manejar_excepcion_no_logger():
    error_msg = "Test error"
    expected_output = f"❌ Error: {error_msg}\n"

    with patch('sys.stdout', new=io.StringIO()) as fake_out:
        manejar_excepcion(Exception(error_msg))
        assert fake_out.getvalue() == expected_output

def test_manejar_excepcion_with_logger():
    error_msg = "Test error with logger"
    expected_output = f"❌ Error: {error_msg}"
    mock_logger = MagicMock()

    with patch('sys.stdout', new=io.StringIO()):
        manejar_excepcion(Exception(error_msg), logger=mock_logger)

    mock_logger.error.assert_called_once_with(expected_output, exc_info=True)
