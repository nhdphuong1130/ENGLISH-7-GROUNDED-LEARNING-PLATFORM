from uuid import uuid4

from english7.main import app
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.quizzes.domain import QuizDraft, QuizOptions
from english7.modules.quizzes.router import get_quiz_service


class FakeQuizServiceWithModes:
    def __init__(self):
        self.calls = []

    def generate(self, user_id, duration_minutes, difficulty, mode="mixed"):
        self.calls.append((user_id, duration_minutes, difficulty, mode))
        audio_url = "/api/v1/media/audio/37" if mode in ("listening", "mixed") else None
        audio_title = "Unit 5 Skills 2 (Track 37)" if mode in ("listening", "mixed") else None
        return QuizDraft(
            uuid4(),
            duration_minutes,
            difficulty,
            10,
            audio_url=audio_url,
            audio_title=audio_title,
        )

    def options(self):
        return QuizOptions(
            (15, 45, 60), 10, 90, 2, ("listening", "reading", "mixed")
        )


def test_student_requests_listening_quiz_returns_audio_url(client) -> None:
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    service = FakeQuizServiceWithModes()
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_quiz_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/quizzes",
            json={"duration_minutes": 15, "difficulty": "adaptive", "mode": "listening"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["audio_url"] == "/api/v1/media/audio/37"
    assert body["audio_title"] == "Unit 5 Skills 2 (Track 37)"
    assert service.calls == [(student.id, 15, "adaptive", "listening")]


def test_student_requests_reading_quiz_has_no_audio_url(client) -> None:
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    service = FakeQuizServiceWithModes()
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_quiz_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/quizzes",
            json={"duration_minutes": 15, "difficulty": "adaptive", "mode": "reading"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["audio_url"] is None
    assert service.calls == [(student.id, 15, "adaptive", "reading")]


def test_quiz_options_includes_available_modes(client) -> None:
    student = AuthUser.new(
        email="student@example.com", password_hash="unused", role="student"
    )
    service = FakeQuizServiceWithModes()
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_quiz_service] = lambda: service
    try:
        response = client.get("/api/v1/quizzes/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "modes" in body
    assert body["modes"] == ["listening", "reading", "mixed"]


def test_grounded_question_generator_reading_mode():
    from english7.bootstrap import GroundedQuestionGenerator

    frag = type("Frag", (), {
        "id": uuid4(),
        "normalized_text": "This is a meaningful verified text about volunteering in the local park.",
        "review_status": "verified",
        "is_published": True,
    })()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def scalars(self, query):
            class Result:
                def all(inner):
                    return [frag]
            return Result()

        def execute(self, query):
            class Result:
                def all(inner):
                    return []
            return Result()

    generator = GroundedQuestionGenerator(FakeSession)
    questions = generator.generate(
        duration_minutes=15, difficulty="medium", question_count=2, mode="reading"
    )
    assert len(questions) == 2
    for q in questions:
        assert "audio_url" not in q.answer


def test_grounded_question_generator_mixed_mode_sections_and_types():
    from english7.bootstrap import GroundedQuestionGenerator

    frag = type("Frag", (), {
        "id": uuid4(),
        "normalized_text": (
            "Alaska is perhaps the most amazing state in the USA. "
            "It has coastlines facing both the Arctic Ocean and the Pacific Ocean. "
            "Solar energy is a clean and renewable source of power. "
            "They built our school a long time ago in the city."
        ),
        "review_status": "verified",
        "is_published": True,
    })()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def scalars(self, query):
            class Result:
                def all(inner):
                    return [frag]
            return Result()

        def execute(self, query):
            class Result:
                def all(inner):
                    return []
            return Result()

    generator = GroundedQuestionGenerator(FakeSession)
    questions = generator.generate(
        duration_minutes=15, difficulty="medium", question_count=10, mode="mixed"
    )
    assert len(questions) == 10
    types = {q.answer.get("question_type") for q in questions}
    assert "reorder" in types, f"Expected reorder in types: {types}"
    assert "error_correction" in types, f"Expected error_correction in types: {types}"
    assert "reading" in types, f"Expected reading in types: {types}"
    reading_questions = [q for q in questions if q.answer.get("question_type") == "reading"]
    assert reading_questions, "Must have reading questions"
    for rq in reading_questions:
        assert rq.answer.get("passage"), "Reading question must have a non-empty passage"
    sections = {q.answer.get("section") for q in questions}
    assert None not in sections, "All questions must have a section"

