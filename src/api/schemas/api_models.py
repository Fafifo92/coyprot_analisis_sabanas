from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    username: str
    ftp_prefix: Optional[str] = Field(None, max_length=5, description="Firma de 5 letras para la carpeta FTP")
    is_admin: bool = False
    is_active: bool = True
    must_change_password: bool = True
    tokens_balance: int = 0

class UserCreate(UserBase):
    username: str = Field(..., min_length=8, description="El nombre de usuario debe tener al menos 8 caracteres")
    password: str
    ftp_prefix: str = Field(..., min_length=5, max_length=5, description="Exactamente 5 letras")

class UserUpdate(BaseModel):
    ftp_prefix: Optional[str] = Field(None, min_length=5, max_length=5)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    must_change_password: Optional[bool] = None
    tokens_balance: Optional[int] = None
    password: Optional[str] = None # Admin puede forzar reset

class UserSettingsUpdate(BaseModel):
    profile_settings: Optional[dict] = None
    global_aliases: Optional[dict] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    profile_settings: Optional[dict] = None
    global_aliases: Optional[dict] = None
    projects_created: Optional[int] = 0

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
    period: Optional[str] = None # Deprecated, kept for backward compat in DB reads, but dynamic in reports
    pdf_draft: Optional[list] = None
    custom_metadata: Optional[dict] = None

class ProjectCreate(BaseModel):
    case_number: str
    target_phone: str
    target_name: Optional[str] = None
    custom_metadata: Optional[dict] = None
    pass

class ProjectUserUpdate(BaseModel):
    case_number: Optional[str] = None
    target_phone: Optional[str] = None
    target_name: Optional[str] = None
    aliases: Optional[dict] = None
    extra_metadata: Optional[dict] = None
    pdf_draft: Optional[list] = None
    custom_metadata: Optional[dict] = None

class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    aliases: Optional[dict] = None
    extra_metadata: Optional[dict] = None
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
