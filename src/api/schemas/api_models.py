from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    username: str
    is_admin: bool = False
    is_active: bool = True
    must_change_password: bool = True
    tokens_balance: int = 0

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    must_change_password: Optional[bool] = None
    tokens_balance: Optional[int] = None
    password: Optional[str] = None # Admin puede forzar reset

class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str
    must_change_password: bool
    is_admin: bool # Añadido para que el frontend sepa si es admin inmediatamente

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ProjectBase(BaseModel):
    case_number: str
    target_phone: str
    target_name: Optional[str] = None
    period: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    status: str
    error_message: Optional[str] = None
    result_html_path: Optional[str] = None
    result_pdf_path: Optional[str] = None
    result_ftp_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
