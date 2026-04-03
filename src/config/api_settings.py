from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys
from pydantic import ValidationError
from functools import lru_cache

class ApiSettings(BaseSettings):
    # Usamos Field con default para que Pydantic NUNCA lo exija en el .env si no existe.

    # Base de Datos
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./coyprot_api.db")

    # Seguridad JWT
    SECRET_KEY: str = Field(...)
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=10080) # 1 semana

    # Redis / Celery (para fase 2 o background tasks)
    CELERY_ENABLED: bool = Field(default=False) # False para usar BackgroundTasks localmente en Windows sin Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache()
def get_api_settings() -> ApiSettings:
    try:
        return ApiSettings()
    except ValidationError as e:
        print("\n" + "="*70)
        print("🚨 ERROR CRÍTICO DE CONFIGURACIÓN DE SEGURIDAD 🚨")
        print("Falta la variable de entorno obligatoria: 'SECRET_KEY'")
        print("El sistema no puede iniciar de forma segura con una clave por defecto.")
        print("\nPara solucionarlo, añade la siguiente línea a tu archivo '.env':")
        print("SECRET_KEY=tu_clave_secreta_super_segura_aqui_12345")
        print("="*70 + "\n")
        sys.exit(1)
