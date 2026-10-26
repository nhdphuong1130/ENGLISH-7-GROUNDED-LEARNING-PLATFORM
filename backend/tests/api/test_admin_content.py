from uuid import uuid4

from english7.main import app
from english7.modules.admin.content_router import get_admin_content_service
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user


class FakeContentService:
    def list_units(self):
        return [
            {
                "id": uuid4(),
                "textbook_id": uuid4(),
                "number": 1,
                "title": "My Hobbies",
                "is_published": False,
                "version": 1,
                "status": "draft",
            }
        ]


def test_admin_lists_draft_content(client) -> None:
    admin = AuthUser(
        id=uuid4(),
        email="admin@example.com",
        password_hash="hash",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_admin_content_service] = FakeContentService
    try:
        response = client.get("/api/v1/admin/content/units")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "draft"
