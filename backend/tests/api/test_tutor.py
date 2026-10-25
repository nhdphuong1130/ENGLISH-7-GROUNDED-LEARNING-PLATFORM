from datetime import datetime, timedelta, timezone
from uuid import uuid4

from english7.main import app
from english7.modules.ai.contracts import Language
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.retrieval.service import Citation
from english7.modules.tutor.router import get_tutor_service
from english7.modules.tutor.service import TutorAnswer
from english7.modules.tutor.conversations import ConversationRecord, ExchangeRecord


class FakeTutorService:
    def __init__(self) -> None:
        self.calls = []

    def _record(self, user_id, *, conversation_id=None):
        now = datetime.now(timezone.utc)
        return ConversationRecord(
            id=conversation_id or uuid4(),
            user_id=user_id,
            title="Unit 2 health",
            language="vi",
            addressing_preference=None,
            expires_at=now + timedelta(days=90),
            created_at=now,
            updated_at=now,
        )

    def create_conversation(self, user_id, language, title, addressing_preference=None):
        self.calls.append(("create", user_id, language, title, addressing_preference))
        return self._record(user_id)

    def list_conversations(self, user_id):
        return (self._record(user_id),)

    def get_conversation(self, user_id, conversation_id):
        return self._record(user_id, conversation_id=conversation_id), ()

    def delete_conversation(self, user_id, conversation_id):
        self.calls.append(("delete", user_id, conversation_id))
        return True

    def ask(
        self,
        question,
        language,
        *,
        user_id=None,
        upload_id=None,
        conversation_id=None,
        addressing_preference=None,
    ):
        self.calls.append(
            (
                question,
                language,
                user_id,
                upload_id,
                conversation_id,
                addressing_preference,
            )
        )
        return TutorAnswer(
            answer="Tập thể dục mỗi ngày.",
            language=Language.VIETNAMESE,
            citations=(Citation(uuid4(), 22, 20),),
            conversation_id=conversation_id or uuid4(),
        )


def test_authenticated_student_asks_bilingual_tutor(client) -> None:
    fake = FakeTutorService()
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_tutor_service] = lambda: fake
    try:
        response = client.post(
            "/api/v1/tutor/ask",
            json={"question": "How can I stay healthy?", "language": "vi"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["language"] == "vi"
    assert response.json()["citations"][0]["printed_page"] == 20
    assert response.json()["conversation_id"]
    assert fake.calls == [(
        "How can I stay healthy?",
        Language.VIETNAMESE,
        student.id,
        None,
        None,
        None,
    )]


def test_student_can_ask_from_uploaded_image_without_typed_question(client) -> None:
    fake = FakeTutorService()
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    upload_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_tutor_service] = lambda: fake
    try:
        response = client.post(
            "/api/v1/tutor/ask",
            json={"question": "", "language": "vi", "upload_id": str(upload_id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake.calls == [(
        "", Language.VIETNAMESE, student.id, upload_id, None, None
    )]


def test_student_manages_and_asks_in_owned_conversation(client) -> None:
    fake = FakeTutorService()
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_tutor_service] = lambda: fake
    try:
        created = client.post(
            "/api/v1/tutor/conversations",
            json={
                "title": "  Unit 2 health  ",
                "language": "vi",
                "addressing_preference": "cô-em",
            },
        )
        conversation_id = created.json()["id"]
        listed = client.get("/api/v1/tutor/conversations")
        detail = client.get(f"/api/v1/tutor/conversations/{conversation_id}")
        answer = client.post(
            f"/api/v1/tutor/conversations/{conversation_id}/ask",
            json={"question": "Giải thích bài này", "language": "vi"},
        )
        deleted = client.delete(
            f"/api/v1/tutor/conversations/{conversation_id}"
        )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert detail.status_code == 200
    assert detail.json()["exchanges"] == []
    assert answer.status_code == 200
    assert answer.json()["conversation_id"] == conversation_id
    assert deleted.status_code == 204
