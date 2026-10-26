from uuid import uuid4

from english7.db.models import ReviewStatus
from english7.main import app
from english7.modules.admin.router import get_admin_textbook_service
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.textbooks.domain import TextbookFragment


class FakeAdminService:
    def __init__(self, fragment_id, unit_id) -> None:
        self.fragment_id = fragment_id
        self.unit_id = unit_id

    def verify_fragment(self, fragment_id, corrected_text, reviewer_id):
        assert fragment_id == self.fragment_id
        return TextbookFragment(
            id=fragment_id,
            unit_id=self.unit_id,
            pdf_page=10,
            printed_page=8,
            normalized_text=corrected_text,
            review_status=ReviewStatus.VERIFIED,
            is_published=True,
            reviewer_id=reviewer_id,
        )


def test_admin_verifies_fragment(client) -> None:
    fragment_id = uuid4()
    admin = AuthUser.new(
        email="admin@example.com",
        password_hash="not-returned",
        role="admin",
    )
    app.dependency_overrides[get_admin_textbook_service] = lambda: FakeAdminService(
        fragment_id,
        uuid4(),
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = client.patch(
            f"/api/v1/admin/fragments/{fragment_id}/verify",
            json={"normalized_text": "Hobbies are fun."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["review_status"] == "verified"
    assert response.json()["is_published"] is True


def test_student_cannot_verify_fragment(client) -> None:
    student = AuthUser.new(
        email="student@example.com",
        password_hash="not-returned",
        role="student",
    )
    app.dependency_overrides[get_admin_textbook_service] = lambda: FakeAdminService(
        uuid4(),
        uuid4(),
    )
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        response = client.patch(
            f"/api/v1/admin/fragments/{uuid4()}/verify",
            json={"normalized_text": "Hobbies are fun."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_admin_can_get_students_progress_and_chats(client, monkeypatch) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from english7.db.base import Base
    from english7.modules.admin import router as admin_router
    from english7.modules.flashcards.router import get_flashcard_service
    from english7.modules.flashcards.service import FlashcardService
    from english7.modules.flashcards.repository import SQLAlchemyFlashcardRepository

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(admin_router, 'get_session_factory', lambda: factory)
    app.dependency_overrides[get_flashcard_service] = lambda: FlashcardService(SQLAlchemyFlashcardRepository(factory))

    admin = AuthUser.new(
        email="admin@example.com",
        password_hash="not-returned",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        res1 = client.get("/api/v1/admin/students/progress")
        assert res1.status_code == 200
        assert "students" in res1.json()
        assert "total_students" in res1.json()

        res2 = client.get("/api/v1/admin/chats")
        assert res2.status_code == 200
        assert "items" in res2.json()
        assert "total" in res2.json()

        res3 = client.get("/api/v1/admin/decks")
        assert res3.status_code == 200
        assert "items" in res3.json()

        progress_csv = client.get("/api/v1/admin/students/export?format=csv")
        progress_xlsx = client.get("/api/v1/admin/students/export?format=xlsx")
        assert progress_csv.status_code == 200
        assert "text/csv" in progress_csv.headers["content-type"]
        assert progress_xlsx.status_code == 200
        assert progress_xlsx.content.startswith(b"PK")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()



def test_student_cannot_access_admin_monitoring_endpoints(client) -> None:
    student = AuthUser.new(
        email="student@example.com",
        password_hash="not-returned",
        role="student",
    )
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        assert client.get("/api/v1/admin/students/progress").status_code == 403
        assert client.get("/api/v1/admin/chats").status_code == 403
        assert client.get("/api/v1/admin/chat-students").status_code == 403
        assert client.get("/api/v1/admin/decks").status_code == 403
        assert client.get("/api/v1/admin/speaking/voices").status_code == 403
        assert client.get("/api/v1/admin/speaking/history").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_reads_one_continuous_chat_history_per_student(
    client, monkeypatch
) -> None:
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from english7.db.base import Base
    from english7.db.models import Role, TutorChat, TutorConversation, User
    from english7.modules.admin import router as admin_router

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    student_id = uuid4()
    conversation_id = uuid4()
    second_conversation_id = uuid4()
    now = datetime.now(timezone.utc)
    with factory.begin() as session:
        role = Role(name="student")
        session.add(role)
        session.flush()
        session.add(
            User(
                id=student_id,
                email="learner@example.com",
                full_name="Learner",
                password_hash="test",
                role_id=role.id,
            )
        )
        session.add_all(
            [
                TutorConversation(
                id=conversation_id,
                user_id=student_id,
                title="Unit 2 health",
                language="vi",
                expires_at=now + timedelta(days=30),
                ),
                TutorConversation(
                    id=second_conversation_id,
                    user_id=student_id,
                    title="A new chat",
                    language="en",
                    expires_at=now + timedelta(days=30),
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                TutorChat(
                    user_id=student_id,
                    conversation_id=conversation_id,
                    sequence_number=1,
                    question="Xin chào",
                    answer="Chào em!",
                    language="vi",
                    citations=[],
                    created_at=now,
                ),
                TutorChat(
                    user_id=student_id,
                    conversation_id=conversation_id,
                    sequence_number=2,
                    question="Bài này nói gì?",
                    answer="Bài này nói về sức khoẻ.",
                    language="vi",
                    citations=[],
                    created_at=now + timedelta(minutes=1),
                ),
                TutorChat(
                    user_id=student_id,
                    conversation_id=second_conversation_id,
                    sequence_number=1,
                    question="This is a new chat. Is it still my history?",
                    answer="Yes. It belongs to the same student account.",
                    language="en",
                    citations=[],
                    created_at=now + timedelta(minutes=2),
                ),
            ]
        )
    monkeypatch.setattr(admin_router, "get_session_factory", lambda: factory)
    app.dependency_overrides[get_current_user] = lambda: AuthUser.new(
        email="admin@example.com", password_hash="unused", role="admin"
    )
    try:
        listing = client.get("/api/v1/admin/chat-students")
        detail = client.get(
            f"/api/v1/admin/chat-students/{student_id}"
        )
        conversation_csv = client.get(
            f"/api/v1/admin/chat-students/{student_id}/export?format=csv"
        )
        conversation_xlsx = client.get(
            f"/api/v1/admin/chat-students/{student_id}/export?format=xlsx"
        )
        conversation_docx = client.get(
            f"/api/v1/admin/chat-students/{student_id}/export?format=docx"
        )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["student_id"] == str(student_id)
    assert listing.json()["items"][0]["exchange_count"] == 3
    assert listing.json()["items"][0]["student_email"] == "learner@example.com"
    assert detail.status_code == 200
    assert [item["question"] for item in detail.json()["exchanges"]] == [
        "Xin chào",
        "Bài này nói gì?",
        "This is a new chat. Is it still my history?",
    ]
    assert {item["conversation_id"] for item in detail.json()["exchanges"]} == {
        str(conversation_id),
        str(second_conversation_id),
    }
    assert conversation_csv.status_code == 200
    assert "text/csv" in conversation_csv.headers["content-type"]
    assert "Bài này nói gì?" in conversation_csv.content.decode("utf-8-sig")
    assert "This is a new chat" in conversation_csv.content.decode("utf-8-sig")
    assert conversation_xlsx.status_code == 200
    assert conversation_xlsx.content.startswith(b"PK")
    assert conversation_docx.status_code == 200
    assert conversation_docx.content.startswith(b"PK")
