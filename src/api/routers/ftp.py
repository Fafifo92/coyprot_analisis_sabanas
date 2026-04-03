from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pathlib import Path
import logging

from db.session import get_db
from db.models import User, Project, AuditLog
from api.services.security import get_current_user
from services.upload_service import UploadService
from config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{project_id}/upload-ftp")
async def upload_project_to_ftp(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.orm import selectinload
    # Verificar proyecto y dueño, incluyendo la info del usuario
    result = await db.execute(select(Project).options(selectinload(Project.owner)).filter(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not current_user.is_admin and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if project.status not in ["COMPLETED_HTML", "COMPLETED_ALL", "FAILED"]:
        raise HTTPException(status_code=400, detail="El proyecto debe generar su HTML primero antes de poder subirse al FTP.")

    if not project.result_html_path:
        raise HTTPException(status_code=404, detail="No se encontró el reporte HTML generado para este caso.")

    if not settings.ftp_configured():
        raise HTTPException(status_code=503, detail="El servidor FTP no está configurado en las variables de entorno.")

    try:
        html_dir = Path(project.result_html_path).parent.parent
        import re
        safe_case_number = re.sub(r'[<>:"/\\|?*]', '_', str(project.case_number))

        # User prefix logic (ftp_prefix explicitly set, else first 5 chars of username)
        # Using project owner's prefix because an admin might upload it on their behalf
        owner_prefix = project.owner.ftp_prefix if (project.owner and project.owner.ftp_prefix) else current_user.username[:5]
        user_prefix = owner_prefix.lower()
        folder_name = f"reports-casp/{user_prefix}/Caso_{safe_case_number}"

        uploader = UploadService()
        url = uploader.upload(html_dir, folder_name)

        project.result_ftp_url = url

        audit = AuditLog(
            user_id=current_user.id,
            action="FTP_UPLOAD",
            details=f"Uploaded project {project_id} to FTP: {url}"
        )
        db.add(audit)

        await db.commit()

        return {"message": "Proyecto subido al FTP exitosamente.", "url": url}

    except Exception as e:
        logger.exception("Error subiendo reporte al FTP")
        raise HTTPException(status_code=500, detail=f"Error subiendo al FTP: {str(e)}")
