from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Roles y Permisos
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True) # Para soft-delete / bloqueo
    must_change_password = Column(Boolean, default=True) # Obligar a cambiar clave en primer login

    # Tokens
    tokens_balance = Column(Integer, default=0) # Cuántos proyectos puede crear

    # Configuración de perfil e informe
    profile_settings = Column(JSON, default={})
    global_aliases = Column(JSON, default={})

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    projects = relationship("Project", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")

class Project(Base):
    """
    Project (AnalysisJob): Representa 1 token gastado y 1 caso a analizar.
    Los datos del caso (objetivo) quedan fijos aquí para evitar re-uso.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    # Datos del Caso (Fijos tras la creación)
    case_number = Column(String, nullable=False)     # Usado para nombrar exportables
    target_phone = Column(String, nullable=False)    # Teléfono objetivo a validar
    target_name = Column(String, nullable=True)
    period = Column(String, nullable=True)

    # Enriquecimiento y Metadatos Extra
    aliases = Column(JSON, default={})
    extra_metadata = Column(JSON, default={})

    # Estado del Job de Análisis
    # PENDING_FILES -> MAPPING -> PROCESSING -> COMPLETED | FAILED
    status = Column(String, default="PENDING_FILES")
    error_message = Column(Text, nullable=True)

    # Exportables (Links o Paths)
    result_html_path = Column(String, nullable=True)
    result_pdf_path = Column(String, nullable=True)
    result_ftp_url = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    owner = relationship("User", back_populates="projects")
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    attachments = relationship("ProjectAttachment", back_populates="project", cascade="all, delete-orphan")

class ProjectAttachment(Base):
    """
    Documentos adjuntos (PDF) como financieros o judiciales.
    """
    __tablename__ = "project_attachments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))

    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    category = Column(String, nullable=False) # Financiero, Propiedades, etc.

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="attachments")

class ProjectFile(Base):
    """
    Archivos Excel/CSV subidos a un proyecto. Guarda también su configuración de mapeo.
    """
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))

    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False) # Dónde se guardó temporalmente el original

    # JSON con el estado de las hojas (raw_sheets info)
    # Ej: ["Hoja1", "Hoja2"]
    detected_sheets = Column(JSON, nullable=True)

    # Mapeos configurados por el usuario
    # Ej: [{"sheet_name": "Hoja1", "sheet_type": "Entrantes", "mapping": {"fecha_hora": "Date", ...}}]
    sheet_configs = Column(JSON, nullable=True)

    # Estado del archivo (UPLOADED, MAPPED, PROCESSED)
    status = Column(String, default="UPLOADED")

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="files")

class AuditLog(Base):
    """
    Registro de auditoría para el Super Admin
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    action = Column(String, nullable=False) # LOGIN, CREATE_PROJECT, ANALYZE_PROJECT, EXPORT
    details = Column(Text, nullable=True)   # "User created project XYZ for target 3001234567"

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")
