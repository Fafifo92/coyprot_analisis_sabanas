"""
Servicio de carga remota por FTP.

Encapsula la conexión FTP con TLS y la subida recursiva de carpetas.
Las credenciales se obtienen siempre de la configuración (variables de entorno).
"""
from __future__ import annotations

import logging
import os
from ftplib import FTP_TLS
from pathlib import Path

from config.settings import settings
from core.exceptions import FtpConnectionError, FtpCredentialsError

logger = logging.getLogger(__name__)


class UploadService:
    """
    Servicio de carga FTP con TLS.

    Principio S: solo maneja la transferencia de archivos al servidor.
    Principio D: recibe la configuración por inyección.
    """

    def __init__(
        self,
        host: str = "",
        user: str = "",
        password: str = "",
        public_html: str = "public_html",
    ) -> None:
        # Si no se pasan credenciales, las toma del settings (variables de entorno)
        self._host = host or settings.ftp_host
        self._user = user or settings.ftp_user
        self._password = password or settings.ftp_pass
        self._public_html = public_html or settings.ftp_public_html

    def upload(self, local_dir: Path, remote_folder: str) -> str:
        """
        Sube el directorio local completo al servidor FTP.

        Args:
            local_dir: Carpeta local a subir.
            remote_folder: Nombre de la carpeta en public_html.

        Returns:
            URL pública del informe.

        Raises:
            FtpCredentialsError: si las credenciales no están configuradas.
            FtpConnectionError: si no se puede conectar al servidor.
        """
        if not all([self._host, self._user, self._password]):
            raise FtpCredentialsError(
                "Credenciales FTP no configuradas. "
                "Defina FTP_HOST, FTP_USER y FTP_PASS en el archivo .env"
            )

        try:
            ftp = FTP_TLS()
            ftp.connect(self._host, 21)
            ftp.login(self._user, self._password)
            ftp.prot_p()
            logger.info("Conectado al FTP con TLS: %s", self._host)

            ftp.cwd(self._public_html)
            self._ensure_remote_path(ftp, remote_folder)
            self._upload_directory(ftp, local_dir)

            ftp.quit()
            url = f"https://{self._host}/{remote_folder}/reports/informe_llamadas.html"
            logger.info("Subida completada: %s", url)
            return url

        except FtpCredentialsError:
            raise
        except Exception as exc:
            raise FtpConnectionError(f"Error en la conexión FTP: {exc}") from exc

    # ── Helpers privados ──────────────────────────────────────────────────────

    @staticmethod
    def _list_names(ftp: FTP_TLS) -> set[str]:
        """Devuelve solo los nombres (sin ruta) del directorio actual."""
        try:
            return {os.path.basename(p) for p in ftp.nlst()}
        except Exception:
            return set()

    def _ensure_remote_path(self, ftp: FTP_TLS, path: str) -> None:
        """Crea y navega a la ruta remota, creando subdirectorios si es necesario."""
        for part in path.strip("/").split("/"):
            if not part:
                continue
            if part not in self._list_names(ftp):
                try:
                    ftp.mkd(part)
                except Exception:
                    pass
            ftp.cwd(part)

    def _upload_directory(self, ftp: FTP_TLS, local_dir: Path) -> None:
        """Sube recursivamente todos los archivos del directorio."""
        base = local_dir.resolve()
        for root, _dirs, files in os.walk(base):
            rel = Path(root).relative_to(base)
            parts = rel.parts

            if parts:
                for part in parts:
                    if part not in self._list_names(ftp):
                        try:
                            ftp.mkd(part)
                        except Exception:
                            pass
                    ftp.cwd(part)

            for filename in files:
                local_file = Path(root) / filename
                with open(local_file, "rb") as fh:
                    ftp.storbinary(f"STOR {filename}", fh)
                    logger.debug("Subido: %s", local_file)

            if parts:
                for _ in parts:
                    ftp.cwd("..")
