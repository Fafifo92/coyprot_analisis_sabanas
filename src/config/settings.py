"""
Módulo de configuración central.

Carga parámetros desde variables de entorno (.env) con valores por defecto seguros.
NUNCA hardcodear credenciales en el código fuente.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_app_dir() -> Path:
    """Resuelve el directorio raíz de la aplicación, compatible con PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def _load_dotenv(app_dir: Path) -> None:
    """Carga variables de .env si el archivo existe (sin dependencia externa)."""
    env_file = app_dir / ".env"
    if not env_file.exists():
        return
    with env_file.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


# ── Inicializar ──────────────────────────────────────────────────────────────
APP_DIR: Path = _resolve_app_dir()
_load_dotenv(APP_DIR)


class Settings:
    """
    Centraliza toda la configuración de la aplicación.

    Los valores sensibles (credenciales FTP) se leen exclusivamente desde
    variables de entorno para evitar que queden expuestos en el código fuente.
    """

    # ── Directorios ──────────────────────────────────────────────────────────
    app_dir: Path = APP_DIR
    output_dir: Path = APP_DIR / "output"
    static_dir: Path = APP_DIR / "static"
    templates_dir: Path = APP_DIR / "templates"
    logs_dir: Path = APP_DIR / "logs"

    # ── Recursos estáticos ───────────────────────────────────────────────────
    logo_path: Path = APP_DIR / "static" / "assets_img" / "logo.png"
    info_icon_path: Path = APP_DIR / "static" / "assets_img" / "info.png"
    cell_db_path: Path = APP_DIR / "static" / "db" / "celdas.csv"
    municipalities_db_path: Path = APP_DIR / "static" / "db" / "municipios_colombia.csv"

    # ── FTP (solo desde variables de entorno) ──────────────────────────────
    ftp_host: str = os.environ.get("FTP_HOST", "")
    ftp_user: str = os.environ.get("FTP_USER", "")
    ftp_pass: str = os.environ.get("FTP_PASS", "")
    ftp_public_html: str = os.environ.get("FTP_PUBLIC_HTML", "public_html")

    # ── Aplicación ───────────────────────────────────────────────────────────
    app_title: str = "Analizador de Llamadas Pro v3.0"
    app_version: str = "3.0.0"
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    log_filename: str = "app.log"

    # ── Geografía ────────────────────────────────────────────────────────────
    # Radio máximo en km para considerar un municipio como "cercano"
    geo_proximity_km: float = float(os.environ.get("GEO_PROXIMITY_KM", "50"))

    @classmethod
    def ftp_configured(cls) -> bool:
        """Devuelve True si las credenciales FTP están configuradas."""
        return bool(cls.ftp_host and cls.ftp_user and cls.ftp_pass)

    @classmethod
    def ensure_dirs(cls) -> None:
        """Crea los directorios necesarios si no existen."""
        for d in [cls.output_dir, cls.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)


# Instancia global (Singleton de configuración)
settings = Settings()
