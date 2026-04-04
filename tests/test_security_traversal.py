import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from pathlib import Path
import os
import shutil

# Mock before importing app to avoid database connections etc if they are at module level
# But usually we mock the dependencies in FastAPI.

from api.main import app
from db.models import User, Project

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.is_admin = False
    return user

@pytest.fixture
def mock_project():
    project = MagicMock(spec=Project)
    project.id = 1
    project.owner_id = 1
    project.status = "PENDING_FILES"
    return project

from api.services.security import get_current_user
from db.session import get_db

@patch("api.routers.attachments.ProjectRepository")
@patch("api.routers.attachments.AuditRepository")
def test_upload_attachment_path_traversal(mock_audit_repo_cls, mock_project_repo_cls, client, mock_user, mock_project):
    # Setup mocks
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    mock_project_repo = mock_project_repo_cls.return_value
    mock_attachment = MagicMock()
    mock_attachment.id = 1
    mock_attachment.filename = "passwd.pdf"
    mock_attachment.file_path = "/fake/path/passwd.pdf"
    mock_attachment.category = "test_category"

    mock_project_repo.get_by_id = AsyncMock(return_value=mock_project)
    mock_project_repo.create_attachment = AsyncMock(return_value=mock_attachment)

    mock_audit_repo = mock_audit_repo_cls.return_value
    mock_audit_repo.log_action = AsyncMock()

    # Malicious filename
    malicious_filename = "../../../etc/passwd.pdf"
    file_content = b"fake pdf content"

    # Target project_id
    project_id = 1

    # Perform upload
    response = client.post(
        f"/api/projects/{project_id}/attachments",
        data={"category": "test_category"},
        files={"file": (malicious_filename, file_content, "application/pdf")}
    )

    # Check response
    assert response.status_code == 200

    # Verify that the repository was called with the sanitized filename
    # safe_filename should be "passwd.pdf"
    expected_safe_filename = "passwd.pdf"

    args, kwargs = mock_project_repo.create_attachment.call_args
    # create_attachment(project.id, safe_filename, str(file_path), category)
    assert args[0] == project_id
    assert args[1] == expected_safe_filename
    assert expected_safe_filename in args[2]
    assert "../../" not in args[2]

    # Verify audit log uses safe filename
    audit_args = mock_audit_repo.log_action.call_args[0]
    assert expected_safe_filename in audit_args[2]
    assert "../../" not in audit_args[2]

    # Cleanup any created directories if necessary (though we should mock Path.mkdir or similar if we want to be truly isolated)
    # For now, let's just check if it was handled correctly in the call to create_attachment
