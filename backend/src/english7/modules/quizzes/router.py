from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from english7.api.errors import ApplicationError
from english7.db.models import QuizQuestion
from english7.db.session import get_session_factory
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.quizzes.service import QuizService
from english7.modules.attempts.progress import ProgressService, AttemptResult
from english7.modules.attempts.progress_repository import SQLAlchemyProgressRepository
from english7.modules.knowledge.gap_service import KnowledgeGapService

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


class GenerateQuizRequest(BaseModel):
    duration_minutes: int = Field(gt=0)
    difficulty: str = Field(min_length=1, max_length=30)
    mode: str = Field(default="mixed", max_length=30)


class QuizQuestionItem(BaseModel):
    id: UUID
    prompt: str
    options: list[str] = ["True", "False", "Not given"]
    question_type: str = "multiple_choice"
    section: str | None = None
    passage: str | None = None
    audio_url: str | None = None
    audio_title: str | None = None


class QuizResponse(BaseModel):
    id: UUID
    duration_minutes: int
    difficulty: str
    question_count: int
    audio_url: str | None = None
    audio_title: str | None = None
    questions: list[QuizQuestionItem] = []


class QuizSubmitResponse(BaseModel):
    correct: int
    total: int


class ProgressResponse(BaseModel):
    completed_quizzes: int
    correct: int
    total: int
    history: list[AttemptResult]


def require_student(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    if user.role != 'student':
        raise ApplicationError('forbidden', 'Student role is required', 403)
    return user


def get_progress_service() -> ProgressService:
    return ProgressService(SQLAlchemyProgressRepository(get_session_factory()))


@router.get('/progress', response_model=ProgressResponse)
def student_progress(
    user: Annotated[AuthUser, Depends(require_student)],
    service: Annotated[ProgressService, Depends(get_progress_service)],
) -> dict:
    return service.progress(user.id)


class KnowledgeGapItemResponse(BaseModel):
    concept_key: str
    concept_name: str
    category: str
    unit_number: int
    unit_title: str
    mastery_score: float
    total_attempts: int
    incorrect_count: int
    summary: str
    textbook_citation: str
    suggested_prompt: str


class KnowledgeGapResponse(BaseModel):
    total_tested_concepts: int
    weak_concepts_count: int
    average_mastery: float
    gaps: list[KnowledgeGapItemResponse]


class RemedialQuizRequest(BaseModel):
    concept_key: str = Field(min_length=1, max_length=100)


def get_knowledge_gap_service(request: Request) -> KnowledgeGapService:
    service = getattr(request.app.state, "knowledge_gap_service", None)
    if service is None:
        service = KnowledgeGapService(get_session_factory())
    return service


@router.get("/knowledge-gap", response_model=KnowledgeGapResponse)
def get_knowledge_gap(
    user: Annotated[AuthUser, Depends(require_student)],
    service: Annotated[KnowledgeGapService, Depends(get_knowledge_gap_service)],
) -> KnowledgeGapResponse:
    analysis = service.diagnose_gaps(user.id)
    return KnowledgeGapResponse(
        total_tested_concepts=analysis.total_tested_concepts,
        weak_concepts_count=analysis.weak_concepts_count,
        average_mastery=round(analysis.average_mastery, 2),
        gaps=[
            KnowledgeGapItemResponse(
                concept_key=g.concept_key,
                concept_name=g.concept_name,
                category=g.category,
                unit_number=g.unit_number,
                unit_title=g.unit_title,
                mastery_score=round(g.mastery_score, 2),
                total_attempts=g.total_attempts,
                incorrect_count=g.incorrect_count,
                summary=g.summary,
                textbook_citation=g.textbook_citation,
                suggested_prompt=g.suggested_prompt,
            )
            for g in analysis.gaps
        ],
    )


class QuizOptionsResponse(BaseModel):
    preset_durations: tuple[int, ...]
    custom_minimum_minutes: int
    custom_maximum_minutes: int
    max_audio_plays: int
    modes: list[str] = ["listening", "reading", "mixed"]


def get_quiz_service(request: Request) -> QuizService:
    service = getattr(request.app.state, "quiz_service", None)
    if service is None:
        raise ApplicationError(
            "quiz_service_unavailable", "Quiz service is not configured", 503
        )
    return service


@router.get("/options", response_model=QuizOptionsResponse)
def quiz_options(
    _user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[QuizService, Depends(get_quiz_service)],
) -> QuizOptionsResponse:
    options = service.options()
    return QuizOptionsResponse(
        preset_durations=options.preset_durations,
        custom_minimum_minutes=options.custom_minimum_minutes,
        custom_maximum_minutes=options.custom_maximum_minutes,
        max_audio_plays=options.max_audio_plays,
        modes=list(options.modes),
    )


@router.post("", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    payload: GenerateQuizRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[QuizService, Depends(get_quiz_service)],
) -> QuizResponse:
    draft = service.generate(
        user.id, payload.duration_minutes, payload.difficulty, payload.mode
    )
    questions: list[QuizQuestionItem] = []
    audio_url = draft.audio_url
    audio_title = draft.audio_title
    try:
        with get_session_factory()() as session:
            db_questions = session.scalars(
                select(QuizQuestion).where(QuizQuestion.quiz_id == draft.id)
            ).all()
            questions = [
                QuizQuestionItem(
                    id=q.id,
                    prompt=q.prompt,
                    options=list(
                        (q.answer_payload or {}).get(
                            "options", ["True", "False", "Not given"]
                        )
                    ),
                    question_type=(q.answer_payload or {}).get(
                        "question_type", q.question_type or "multiple_choice"
                    ),
                    section=(q.answer_payload or {}).get("section"),
                    passage=(q.answer_payload or {}).get("passage"),
                    audio_url=(q.answer_payload or {}).get("audio_url"),
                    audio_title=(q.answer_payload or {}).get("audio_title"),
                )
                for q in db_questions
            ]
            def _sec_key(item: QuizQuestionItem) -> str:
                s = (item.section or "").upper()
                if "PHẦN A" in s:
                    return "1"
                if "PHẦN B" in s:
                    return "2"
                if "PHẦN C" in s:
                    return "3"
                if "PHẦN D" in s:
                    return "4"
                return "5"
            questions.sort(key=_sec_key)
            if not audio_url:
                for q in db_questions:
                    if (q.answer_payload or {}).get("audio_url"):
                        audio_url = q.answer_payload["audio_url"]
                        audio_title = q.answer_payload.get("audio_title")
                        break
    except Exception:
        pass
    return QuizResponse(
        id=draft.id,
        duration_minutes=draft.duration_minutes,
        difficulty=draft.difficulty,
        question_count=draft.question_count,
        audio_url=audio_url,
        audio_title=audio_title,
        questions=questions,
    )


@router.post("/remedial", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def generate_remedial_quiz(
    payload: RemedialQuizRequest,
    user: Annotated[AuthUser, Depends(require_student)],
    service: Annotated[QuizService, Depends(get_quiz_service)],
) -> QuizResponse:
    draft = service.generate(
        user.id, duration_minutes=15, difficulty="medium", mode="reading"
    )
    questions: list[QuizQuestionItem] = []
    audio_url = draft.audio_url
    audio_title = draft.audio_title
    try:
        with get_session_factory()() as session:
            db_questions = session.scalars(
                select(QuizQuestion).where(QuizQuestion.quiz_id == draft.id)
            ).all()
            questions = [
                QuizQuestionItem(
                    id=q.id,
                    prompt=q.prompt,
                    options=list(
                        (q.answer_payload or {}).get(
                            "options", ["True", "False", "Not given"]
                        )
                    ),
                    question_type=(q.answer_payload or {}).get(
                        "question_type", q.question_type or "multiple_choice"
                    ),
                    section=(q.answer_payload or {}).get("section"),
                    passage=(q.answer_payload or {}).get("passage"),
                    audio_url=(q.answer_payload or {}).get("audio_url"),
                    audio_title=(q.answer_payload or {}).get("audio_title"),
                )
                for q in db_questions
            ]
            def _sec_key(item: QuizQuestionItem) -> str:
                s = (item.section or "").upper()
                if "PHẦN A" in s:
                    return "1"
                if "PHẦN B" in s:
                    return "2"
                if "PHẦN C" in s:
                    return "3"
                if "PHẦN D" in s:
                    return "4"
                return "5"
            questions.sort(key=_sec_key)
    except Exception:
        pass
    return QuizResponse(
        id=draft.id,
        duration_minutes=draft.duration_minutes,
        difficulty=draft.difficulty,
        question_count=len(questions) or draft.question_count,
        audio_url=audio_url,
        audio_title=audio_title,
        questions=questions,
    )


class SubmitQuizRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


@router.post("/{quiz_id}/submit", response_model=QuizSubmitResponse)
def submit_quiz(
    quiz_id: UUID,
    user: Annotated[AuthUser, Depends(require_student)],
    service: Annotated[ProgressService, Depends(get_progress_service)],
    payload: SubmitQuizRequest | None = None,
) -> QuizSubmitResponse:
    result = service.submit(user.id, quiz_id, payload.answers if payload else {})
    return QuizSubmitResponse(correct=result.correct, total=result.total)
