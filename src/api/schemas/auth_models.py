from pydantic import BaseModel, ConfigDict

class UserMeResponse(BaseModel):
    username: str
    is_admin: bool
    tokens_balance: int
    projects_created: int

    model_config = ConfigDict(from_attributes=True)
