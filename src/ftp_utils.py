from ftplib import FTP_TLS
import os


def subir_archivo_ftp(ftp_host, ftp_user, ftp_pass, carpeta_local, carpeta_remota):
    try:
        ftps = FTP_TLS()
        ftps.connect(ftp_host, 21)
        ftps.login(ftp_user, ftp_pass)
        ftps.prot_p()
        print("🔐 Conectado al FTP con TLS")

        # Ir a public_html
        ftps.cwd("public_html")

        # Crear y entrar a la carpeta_remota (puede tener subcarpetas)
        for subdir in carpeta_remota.strip("/").split("/"):
            if subdir not in ftps.nlst():
                try:
                    ftps.mkd(subdir)
                except:
                    pass  # Ya existe
            ftps.cwd(subdir)

        subir_directorio(ftp=ftps, local_path=carpeta_local)

        ftps.quit()
        print("✅ Subida completada correctamente.")
        return True

    except Exception as e:
        print(f"❌ Error al subir al FTP: {e}")
        return False


def subir_directorio(ftp, local_path):
    base_dir = os.path.abspath(local_path)
    for root, dirs, files in os.walk(base_dir):
        rel_path = os.path.relpath(root, base_dir).replace("\\", "/")

        # Crear subdirectorios uno por uno si es necesario
        if rel_path != ".":
            for subfolder in rel_path.split("/"):
                if subfolder not in ftp.nlst():
                    try:
                        ftp.mkd(subfolder)
                    except:
                        pass
                ftp.cwd(subfolder)

        for file in files:
            local_file = os.path.join(root, file)
            with open(local_file, "rb") as f:
                ftp.storbinary(f"STOR {file}", f)

        # Volver a raíz tras cada carpeta
        if rel_path != ".":
            for _ in rel_path.split("/"):
                ftp.cwd("..")