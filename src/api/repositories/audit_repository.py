from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from db.models import AuditLog

class AuditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[AuditLog]:
        result = await self.db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))
        return result.scalars().all()

    async def log_action(self, user_id: int, action: str, details: str = None) -> AuditLog:
        audit = AuditLog(user_id=user_id, action=action, details=details)
        self.db.add(audit)
        await self.db.flush()
        return audit
