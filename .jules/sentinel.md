## 2024-05-24 - Prevent Path Traversal
**Vulnerability:** When uploading files, trusting `file.filename` directly from the request can lead to path traversal if the filename contains `../` sequences, allowing attackers to overwrite arbitrary files on the server.
**Learning:** This is a common attack vector in Python web frameworks (FastAPI/Flask) where uploaded files are written to the filesystem.
**Prevention:** Always use `Path(file.filename).name` (or `os.path.basename`) to extract only the actual filename and strip away any directory traversal components before saving to the filesystem.