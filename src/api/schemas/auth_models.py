from pydantic import BaseModel, ConfigDict

from typing import Optional

class UserMeResponse(BaseModel):
    username: str
    is_admin: bool
    tokens_balance: int
    projects_created: int
    profile_settings: Optional[dict] = None
    global_aliases: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)
