from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from db.models import User
from api.services.security import get_password_hash

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(select(User).filter(User.username == username))
        return result.scalars().first()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).filter(User.id == user_id))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        result = await self.db.execute(select(User).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, user_in: dict) -> User:
        hashed_password = get_password_hash(user_in["password"])
        new_user = User(
            username=user_in["username"],
            hashed_password=hashed_password,
            ftp_prefix=user_in.get("ftp_prefix"),
            is_admin=user_in.get("is_admin", False),
            tokens_balance=user_in.get("tokens_balance", 0),
            must_change_password=True,
            is_active=True
        )
        self.db.add(new_user)
        await self.db.flush() # Flush to get ID, commit later
        return new_user

    async def update(self, user: User, update_data: dict) -> User:
        if "password" in update_data:
            user.hashed_password = get_password_hash(update_data["password"])
            user.must_change_password = True
            del update_data["password"]

        for key, value in update_data.items():
            setattr(user, key, value)

        await self.db.flush()
        return user

    async def soft_delete(self, user: User) -> None:
        user.is_active = False
        await self.db.flush()
