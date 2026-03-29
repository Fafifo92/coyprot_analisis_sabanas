## 2024-05-24 - Default Secret Key Vulnerability
**Vulnerability:** A hardcoded default `SECRET_KEY` was found in `src/config/api_settings.py` for JWT signing. This allows anyone with access to the source code to forge authentication tokens if the default is not overridden in production.
**Learning:** Default values for sensitive credentials in configuration models (like Pydantic's `BaseSettings`) can easily leak into production environments, breaking the "fail-fast" principle.
**Prevention:** Remove default values for sensitive fields in configuration schemas, forcing the application to crash on startup if the required environment variables are missing. Explicitly define required fields (e.g., using `Field(...)` in Pydantic).

## 2024-10-25 - Path Traversal Vulnerability in File Upload
**Vulnerability:** The `upload_file` endpoint in `src/api/routers/files.py` directly concatenated `file.filename` to the upload directory path. Since `file.filename` is supplied by the user, an attacker could craft a payload with `../` (e.g., `../../../etc/passwd`) to write files outside the intended project directory.
**Learning:** Using raw client-provided filenames directly in filesystem path creation is a dangerous pattern in any web application allowing file uploads.
**Prevention:** Always sanitize the filename before using it in a path. Using `Path(filename).name` securely strips off any directory components (like `../`), ensuring the file is saved exactly within the target directory.
