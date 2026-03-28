## 2024-05-24 - Default Secret Key Vulnerability
**Vulnerability:** A hardcoded default `SECRET_KEY` was found in `src/config/api_settings.py` for JWT signing. This allows anyone with access to the source code to forge authentication tokens if the default is not overridden in production.
**Learning:** Default values for sensitive credentials in configuration models (like Pydantic's `BaseSettings`) can easily leak into production environments, breaking the "fail-fast" principle.
**Prevention:** Remove default values for sensitive fields in configuration schemas, forcing the application to crash on startup if the required environment variables are missing. Explicitly define required fields (e.g., using `Field(...)` in Pydantic).
