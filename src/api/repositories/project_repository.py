from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from db.models import Project, ProjectFile, ProjectAttachment

class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Project]:
        result = await self.db.execute(select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit))
        return result.scalars().all()

    async def get_by_id(self, project_id: int) -> Optional[Project]:
        result = await self.db.execute(select(Project).filter(Project.id == project_id))
        return result.scalars().first()

    async def get_by_id_with_files(self, project_id: int) -> Optional[Project]:
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.files))
            .filter(Project.id == project_id)
        )
        return result.scalars().first()

    async def get_by_owner(self, owner_id: int, skip: int = 0, limit: int = 100) -> List[Project]:
        result = await self.db.execute(
            select(Project)
            .filter(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc())
            .offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, owner_id: int, project_data: dict) -> Project:
        new_project = Project(
            owner_id=owner_id,
            case_number=project_data["case_number"],
            target_phone=project_data["target_phone"],
            target_name=project_data.get("target_name"),
            custom_metadata=project_data.get("custom_metadata", {})
        )
        self.db.add(new_project)
        await self.db.flush()
        return new_project

    async def update(self, project: Project, update_data: dict) -> Project:
        # For admin updates
        if "status" in update_data and update_data["status"] in ["PENDING_FILES", "PENDING_MAPPING"]:
            project.error_message = None
            project.result_html_path = None
            project.result_pdf_path = None

            # Reset file statuses to UPLOADED to allow re-mapping
            files = await self.get_files_for_project(project.id)
            for file in files:
                file.status = "UPLOADED"

        for key, value in update_data.items():
            setattr(project, key, value)

        await self.db.flush()
        return project

    async def delete(self, project: Project) -> None:
        await self.db.delete(project)
        await self.db.flush()

    async def get_file_by_id(self, file_id: int, project_id: int) -> Optional[ProjectFile]:
        result = await self.db.execute(
            select(ProjectFile)
            .filter(ProjectFile.id == file_id, ProjectFile.project_id == project_id)
        )
        return result.scalars().first()

    async def get_files_for_project(self, project_id: int) -> List[ProjectFile]:
        result = await self.db.execute(
            select(ProjectFile)
            .filter(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.created_at)
        )
        return result.scalars().all()

    async def create_file(self, project_id: int, filename: str, file_path: str, detected_sheets: dict) -> ProjectFile:
        new_file = ProjectFile(
            project_id=project_id,
            filename=filename,
            file_path=file_path,
            detected_sheets=detected_sheets,
            status="UPLOADED"
        )
        self.db.add(new_file)
        await self.db.flush()
        return new_file

    async def get_attachments_for_project(self, project_id: int) -> List[ProjectAttachment]:
        result = await self.db.execute(
            select(ProjectAttachment)
            .filter(ProjectAttachment.project_id == project_id)
            .order_by(ProjectAttachment.created_at)
        )
        return result.scalars().all()

    async def get_attachment_by_id(self, attachment_id: int, project_id: int) -> Optional[ProjectAttachment]:
        result = await self.db.execute(
            select(ProjectAttachment)
            .filter(ProjectAttachment.id == attachment_id, ProjectAttachment.project_id == project_id)
        )
        return result.scalars().first()

    async def create_attachment(self, project_id: int, filename: str, file_path: str, category: str) -> ProjectAttachment:
        new_att = ProjectAttachment(
            project_id=project_id,
            filename=filename,
            file_path=file_path,
            category=category
        )
        self.db.add(new_att)
        await self.db.flush()
        return new_att

    async def delete_attachment(self, attachment: ProjectAttachment) -> None:
        await self.db.delete(attachment)
        await self.db.flush()
