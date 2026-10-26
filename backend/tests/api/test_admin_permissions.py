from uuid import uuid4

from english7.main import app
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user


def test_student_cannot_read_admin_audit_events(client) -> None:
    student = AuthUser(
        id=uuid4(),
        email="student@example.com",
        password_hash="hash",
        role="student",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        response = client.get("/api/v1/admin/audit-events")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
