from uuid import uuid4

from english7.main import app
from english7.modules.admin.student_service import AdminStudent
from english7.modules.admin.students_router import get_admin_student_service
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user


class FakeAdminStudentService:
    def __init__(self) -> None:
        self.student = AdminStudent(
            id=uuid4(),
            email="student@example.com",
            full_name="Student",
            date_of_birth=None,
            gender=None,
            school_name="School",
            class_name="7A",
            is_active=True,
            archived_at=None,
        )
        self.calls: list[tuple[str, object]] = []

    def list_students(self, **_kwargs):
        return [self.student]

    def get_student(self, _student_id):
        return self.student

    def archive(self, student_id, **kwargs):
        self.calls.append(("archive", (student_id, kwargs)))
        return self.student


def _user(role: str) -> AuthUser:
    return AuthUser(
        id=uuid4(),
        email=f"{role}@example.com",
        password_hash="hash",
        role=role,
        is_active=True,
    )


def test_admin_lists_students(client) -> None:
    service = FakeAdminStudentService()
    app.dependency_overrides[get_current_user] = lambda: _user("admin")
    app.dependency_overrides[get_admin_student_service] = lambda: service
    try:
        response = client.get("/api/v1/admin/students?q=Student&status=active")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["email"] == "student@example.com"


def test_student_cannot_archive_an_account(client) -> None:
    service = FakeAdminStudentService()
    app.dependency_overrides[get_current_user] = lambda: _user("student")
    app.dependency_overrides[get_admin_student_service] = lambda: service
    try:
        response = client.post(
            f"/api/v1/admin/students/{service.student.id}/archive",
            json={"confirmation": service.student.email},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert service.calls == []
