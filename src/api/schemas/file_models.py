from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Optional, Any
from datetime import datetime

class FileUploadResponse(BaseModel):
    id: int
    filename: str
    detected_sheets: Dict[str, List[str]] # { "Hoja1": ["ColA", "ColB"], ... }
    status: str
    sheet_configs: Optional[List[Dict[str, Any]]] = None # Los mapeos guardados si existen

    model_config = ConfigDict(from_attributes=True)

class SheetMappingConfig(BaseModel):
    sheet_name: str
    sheet_type: str  # Entrantes, Salientes, Datos, Generica, Ignorar
    mapping: Dict[str, str] # { "fecha_hora": "Date", "originador": "A_Number" }

class ProjectFileMapRequest(BaseModel):
    configs: List[SheetMappingConfig]
