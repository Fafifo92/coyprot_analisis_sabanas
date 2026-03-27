from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class ApiSettings(BaseSettings):
    # Base de Datos
    DATABASE_URL: str = "sqlite+aiosqlite:///./coyprot_api.db"

    # Seguridad JWT
    SECRET_KEY: str = "super_secret_key_change_in_production_12345"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 semana

    # Redis / Celery (para fase 2 o background tasks)
    CELERY_ENABLED: bool = False # False para usar BackgroundTasks localmente en Windows sin Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache()
def get_api_settings() -> ApiSettings:
    return ApiSettings()
