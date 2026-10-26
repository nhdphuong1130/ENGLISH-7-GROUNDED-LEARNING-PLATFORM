from datetime import datetime
from uuid import uuid4

from english7.main import app
from english7.modules.admin.dashboard_router import get_admin_dashboard_service
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user


class FakeDashboardService:
    def summary(self):
        return {
            "total_students": 12,
            "active_students": 9,
            "locked_students": 2,
            "archived_students": 1,
            "submitted_tests": 5,
            "draft_content": 3,
        }


def test_admin_dashboard_returns_operational_counts(client) -> None:
    admin = AuthUser(
        id=uuid4(),
        email="admin@example.com",
        password_hash="hash",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_admin_dashboard_service] = FakeDashboardService
    try:
        response = client.get("/api/v1/admin/dashboard")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "total_students": 12,
        "active_students": 9,
        "locked_students": 2,
        "archived_students": 1,
        "submitted_tests": 5,
        "draft_content": 3,
        "refreshed_at": response.json()["refreshed_at"],
    }
    assert datetime.fromisoformat(response.json()["refreshed_at"]).tzinfo is not None
