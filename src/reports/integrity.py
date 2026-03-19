"""
Módulo de verificación de integridad de archivos.

Genera hashes SHA-256 y archivos .sha256 de verificación
compatibles con ``sha256sum -c``.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BUFFER_SIZE = 65_536  # 64 KB chunks


def compute_sha256(file_path: Path) -> str:
    """Computa el hash SHA-256 de un archivo.

    Retorna la cadena hexadecimal del hash.
    """
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while True:
            data = f.read(_BUFFER_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def write_sha256_companion(file_path: Path) -> Path:
    """Computa SHA-256 y escribe un archivo ``.sha256`` companion.

    El formato es compatible con ``sha256sum -c``::

        <hash>  <filename>

    Retorna la ruta al archivo .sha256 generado.
    """
    hash_hex = compute_sha256(file_path)
    companion = file_path.with_suffix(file_path.suffix + ".sha256")
    companion.write_text(f"{hash_hex}  {file_path.name}\n", encoding="utf-8")
    logger.info("SHA-256 de %s: %s", file_path.name, hash_hex[:16] + "...")
    return companion
