from unittest.mock import MagicMock
from uuid import uuid4

from english7.main import app
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.knowledge.gap_service import (
    KnowledgeGapAnalysis,
    KnowledgeGapItem,
    KnowledgeGapService,
)
from english7.modules.quizzes.domain import QuizDraft
from english7.modules.quizzes.router import get_knowledge_gap_service, get_quiz_service


class FakeQuizService:
    def __init__(self):
        self.calls = []

    def generate(self, user_id, duration_minutes, difficulty, mode="mixed"):
        self.calls.append((user_id, duration_minutes, difficulty, mode))
        return QuizDraft(uuid4(), duration_minutes, difficulty, 5)


def test_get_knowledge_gap_returns_analysis(client):
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    mock_service = MagicMock(spec=KnowledgeGapService)
    mock_service.diagnose_gaps.return_value = KnowledgeGapAnalysis(
        total_tested_concepts=2,
        weak_concepts_count=1,
        average_mastery=0.45,
        gaps=[
            KnowledgeGapItem(
                concept_key="grammar-u1",
                concept_name="Present Simple Tense",
                category="grammar",
                unit_number=1,
                unit_title="Hobbies",
                mastery_score=0.33,
                total_attempts=3,
                incorrect_count=2,
                summary="Thì hiện tại đơn diễn tả thói quen.",
                textbook_citation="SGK Tiếng Anh 7 Unit 1, Trang 11",
                suggested_prompt="Giải thích thì hiện tại đơn",
            )
        ],
    )

    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_knowledge_gap_service] = lambda: mock_service
    try:
        response = client.get("/api/v1/quizzes/knowledge-gap")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_tested_concepts"] == 2
    assert data["weak_concepts_count"] == 1
    assert data["average_mastery"] == 0.45
    assert len(data["gaps"]) == 1
    assert data["gaps"][0]["concept_key"] == "grammar-u1"
    assert data["gaps"][0]["textbook_citation"] == "SGK Tiếng Anh 7 Unit 1, Trang 11"


def test_post_remedial_quiz_generates_quiz(client):
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    quiz_service = FakeQuizService()

    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_quiz_service] = lambda: quiz_service
    try:
        response = client.post(
            "/api/v1/quizzes/remedial",
            json={"concept_key": "grammar-u1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["question_count"] == 5
    assert len(quiz_service.calls) == 1
    assert quiz_service.calls[0][0] == student.id
