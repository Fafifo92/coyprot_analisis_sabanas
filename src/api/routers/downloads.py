import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.session import get_db
from db.models import User, Project, AuditLog
from api.services.security import get_current_user

router = APIRouter()

@router.get("/{project_id}/download/{format}")
async def download_results(
    project_id: int,
    format: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint para descargar o previsualizar el informe de un proyecto en HTML o PDF.
    """
    # Verificar proyecto y dueño
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    if project.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="El proyecto aún no ha terminado de analizarse o falló.")

    file_path = None
    media_type = "application/octet-stream"
    filename = f"Analisis_Caso_{project.case_number}"

    if format.lower() == "pdf":
        file_path = project.result_pdf_path
        media_type = "application/pdf"
        filename += ".pdf"
    elif format.lower() == "html":
        # Para el HTML interactivo (que incluye mapas y assets), lo mejor es devolver el HTML principal,
        # pero como depende de assets, lo correcto para descarga es empacar toda la carpeta en un ZIP.
        html_dir = Path(project.result_html_path).parent.parent
        zip_path = html_dir.parent / f"Caso_{project.case_number}_completo.zip"

        if not zip_path.exists():
            # Crear zip de la carpeta si no existe
            shutil.make_archive(str(zip_path).replace(".zip", ""), 'zip', html_dir)

        file_path = str(zip_path)
        media_type = "application/zip"
        filename += "_Completo.zip"
    else:
        raise HTTPException(status_code=400, detail="Formato no soportado (usa pdf o html)")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="El archivo solicitado no se encontró en el servidor.")

    # Registrar auditoría de descarga
    audit = AuditLog(
        user_id=current_user.id,
        action="DOWNLOAD_REPORT",
        details=f"Downloaded {format.upper()} report for project {project_id}"
    )
    db.add(audit)
    await db.commit()

    return FileResponse(path=file_path, filename=filename, media_type=media_type)
