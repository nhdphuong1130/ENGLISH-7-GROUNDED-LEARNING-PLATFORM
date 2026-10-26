from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from english7.api.errors import ApplicationError
from english7.db.models import ReviewStatus
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.auth.service import AuthService
from english7.modules.speaking.router import VoiceRequest, get_speaking_service
from english7.modules.speaking.service import MAX_AUDIO_BYTES, SpeakingService
from english7.modules.textbooks.router import get_textbook_service
from english7.modules.textbooks.service import TextbookService

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_textbook_service() -> TextbookService:
    return get_textbook_service()


def get_session_factory():
    from english7.db.session import get_session_factory as _factory

    return _factory()


class VerifyFragmentRequest(BaseModel):
    normalized_text: str = Field(min_length=1)


class AdminFragmentResponse(BaseModel):
    id: UUID
    normalized_text: str
    review_status: ReviewStatus
    is_published: bool
    reviewer_id: UUID | None


class StudentProgressItem(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    school_name: str | None = None
    class_name: str | None = None
    completed_quizzes: int = 0
    total_questions: int = 0
    correct_answers: int = 0
    accuracy_percent: int = 0
    reviewed_cards: int = 0
    due_cards: int = 0
    difficult_cards: int = 0
    speaking_count: int = 0
    recent_quizzes: list[dict[str, Any]] = Field(default_factory=list)


class AdminProgressResponse(BaseModel):
    total_students: int
    total_quizzes: int
    average_accuracy: int
    students: list[StudentProgressItem]


class AdminChatItem(BaseModel):
    id: UUID
    conversation_id: UUID
    user_id: UUID
    user_email: str
    user_name: str | None = None
    question: str
    answer: str
    language: str
    upload_id: UUID | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class AdminChatListResponse(BaseModel):
    total: int
    items: list[AdminChatItem]


class AdminConversationSummary(BaseModel):
    id: UUID
    student_id: UUID
    student_email: str
    student_name: str | None = None
    title: str
    language: str
    exchange_count: int
    created_at: datetime
    updated_at: datetime


class AdminConversationExchange(BaseModel):
    id: UUID
    sequence_number: int
    question: str
    answer: str
    language: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class AdminConversationDetail(BaseModel):
    id: UUID
    student_id: UUID
    student_email: str
    student_name: str | None = None
    title: str
    language: str
    created_at: datetime
    updated_at: datetime
    exchanges: list[AdminConversationExchange]


class AdminChatStudentSummary(BaseModel):
    student_id: UUID
    student_email: str
    student_name: str | None = None
    exchange_count: int
    last_activity_at: datetime


class AdminStudentChatExchange(AdminConversationExchange):
    conversation_id: UUID


class AdminStudentChatHistory(BaseModel):
    student_id: UUID
    student_email: str
    student_name: str | None = None
    exchange_count: int
    last_activity_at: datetime | None = None
    exchanges: list[AdminStudentChatExchange]


@router.patch(
    "/fragments/{fragment_id}/verify",
    response_model=AdminFragmentResponse,
)
def verify_fragment(
    fragment_id: UUID,
    payload: VerifyFragmentRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TextbookService, Depends(get_admin_textbook_service)],
) -> AdminFragmentResponse:
    AuthService.authorize(user, {"admin"})
    fragment = service.verify_fragment(
        fragment_id,
        corrected_text=payload.normalized_text,
        reviewer_id=user.id,
    )
    return AdminFragmentResponse(
        id=fragment.id,
        normalized_text=fragment.normalized_text,
        review_status=fragment.review_status,
        is_published=fragment.is_published,
        reviewer_id=fragment.reviewer_id,
    )


@router.get("/students/progress", response_model=AdminProgressResponse)
def get_students_progress(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AdminProgressResponse:
    AuthService.authorize(user, {"admin"})
    from english7.db.models import Role, User
    from english7.modules.attempts.progress_repository import (
        SQLAlchemyProgressRepository,
    )
    from english7.modules.flashcards.repository import (
        SQLAlchemyFlashcardRepository,
    )
    from english7.modules.flashcards.service import FlashcardService
    from english7.modules.speaking.models import SpeakingAttempt

    session_factory = get_session_factory()
    progress_repo = SQLAlchemyProgressRepository(session_factory)
    flashcard_service = FlashcardService(
        SQLAlchemyFlashcardRepository(session_factory)
    )

    students_data: list[StudentProgressItem] = []
    total_quizzes_all = 0
    total_correct_all = 0
    total_questions_all = 0

    with session_factory() as session:
        student_role = session.query(Role).filter_by(name="student").first()
        if not student_role:
            return AdminProgressResponse(
                total_students=0,
                total_quizzes=0,
                average_accuracy=0,
                students=[],
            )

        students = session.query(User).filter_by(role_id=student_role.id).all()
        for s in students:
            history = progress_repo.history(s.id)
            completed_quizzes = len(history)
            correct_answers = sum(item.correct for item in history)
            total_questions = sum(item.total for item in history)
            accuracy_percent = (
                round(100 * correct_answers / total_questions)
                if total_questions > 0
                else 0
            )

            recent_quizzes = [
                {
                    "quiz_id": str(item.quiz_id),
                    "submitted_at": (
                        item.submitted_at.isoformat()
                        if item.submitted_at
                        else None
                    ),
                    "correct": item.correct,
                    "total": item.total,
                }
                for item in history[:5]
            ]

            card_progress = flashcard_service.progress(s.id)
            speaking_count = (
                session.query(SpeakingAttempt)
                .filter(SpeakingAttempt.user_id == s.id)
                .count()
            )

            students_data.append(
                StudentProgressItem(
                    id=s.id,
                    email=s.email,
                    full_name=s.full_name,
                    school_name=s.school_name,
                    class_name=s.class_name,
                    completed_quizzes=completed_quizzes,
                    total_questions=total_questions,
                    correct_answers=correct_answers,
                    accuracy_percent=accuracy_percent,
                    reviewed_cards=card_progress.get("reviewed_cards", 0),
                    due_cards=card_progress.get("due_cards", 0),
                    difficult_cards=card_progress.get("difficult_cards", 0),
                    speaking_count=speaking_count,
                    recent_quizzes=recent_quizzes,
                )
            )

            total_quizzes_all += completed_quizzes
            total_correct_all += correct_answers
            total_questions_all += total_questions

    avg_accuracy = (
        round(100 * total_correct_all / total_questions_all)
        if total_questions_all > 0
        else 0
    )
    return AdminProgressResponse(
        total_students=len(students_data),
        total_quizzes=total_quizzes_all,
        average_accuracy=avg_accuracy,
        students=students_data,
    )


@router.get("/students/export")
def export_students_progress(
    user: Annotated[AuthUser, Depends(get_current_user)],
    format: str = Query(default="xlsx", pattern="^(csv|xlsx)$"),
) -> Response:
    AuthService.authorize(user, {"admin"})
    from english7.modules.admin.exports import (
        student_progress_csv,
        student_progress_xlsx,
    )

    progress = get_students_progress(user)
    students = [item.model_dump() for item in progress.students]
    if format == "xlsx":
        content = student_progress_xlsx(students)
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        content = student_progress_csv(students)
        media_type = "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="student-progress.{format}"'
        },
    )


@router.get("/chats", response_model=AdminChatListResponse)
def get_admin_chats(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AdminChatListResponse:
    AuthService.authorize(user, {"admin"})
    from english7.db.models import TutorChat, User

    session_factory = get_session_factory()
    items: list[AdminChatItem] = []

    with session_factory() as session:
        chats = (
            session.query(TutorChat)
            .order_by(TutorChat.created_at.desc())
            .limit(200)
            .all()
        )
        for chat in chats:
            u = session.query(User).filter_by(id=chat.user_id).first()
            items.append(
                AdminChatItem(
                    id=chat.id,
                    conversation_id=chat.conversation_id,
                    user_id=chat.user_id,
                    user_email=u.email if u else "unknown",
                    user_name=u.full_name if u else None,
                    question=chat.question,
                    answer=chat.answer,
                    language=chat.language,
                    upload_id=chat.upload_id,
                    citations=chat.citations or [],
                    created_at=chat.created_at,
                )
            )

    return AdminChatListResponse(
        total=len(items),
        items=items,
    )


@router.get("/conversations")
def get_admin_conversations(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> dict[str, Any]:
    AuthService.authorize(user, {"admin"})
    from english7.modules.admin.monitoring import AdminMonitoringService

    items = AdminMonitoringService(get_session_factory()).list_conversations()
    return {
        "total": len(items),
        "items": [AdminConversationSummary(**item) for item in items],
    }


@router.get("/chat-students")
def get_admin_chat_students(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> dict[str, Any]:
    AuthService.authorize(user, {"admin"})
    from english7.modules.admin.monitoring import AdminMonitoringService

    items = AdminMonitoringService(get_session_factory()).list_chat_students()
    return {
        "total": len(items),
        "items": [AdminChatStudentSummary(**item) for item in items],
    }


@router.get(
    "/chat-students/{student_id}",
    response_model=AdminStudentChatHistory,
)
def get_admin_student_chat_history(
    student_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AdminStudentChatHistory:
    AuthService.authorize(user, {"admin"})
    from english7.modules.admin.monitoring import AdminMonitoringService

    return AdminStudentChatHistory(
        **AdminMonitoringService(get_session_factory()).student_chat_history(
            student_id
        )
    )


@router.get("/chat-students/{student_id}/export")
def export_admin_student_chat_history(
    student_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    format: str = Query(default="csv", pattern="^(csv|xlsx|docx)$"),
) -> Response:
    AuthService.authorize(user, {"admin"})
    from english7.modules.admin.exports import (
        student_chat_csv,
        student_chat_docx,
        student_chat_xlsx,
    )
    from english7.modules.admin.monitoring import AdminMonitoringService

    history = AdminMonitoringService(
        get_session_factory()
    ).student_chat_history(student_id)
    if format == "docx":
        content = student_chat_docx(history)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    elif format == "xlsx":
        content = student_chat_xlsx(history)
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        content = student_chat_csv(history)
        media_type = "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="student-chat-{student_id}.{format}"'
            )
        },
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=AdminConversationDetail,
)
def get_admin_conversation(
    conversation_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AdminConversationDetail:
    AuthService.authorize(user, {"admin"})
    from english7.modules.admin.monitoring import AdminMonitoringService

    return AdminConversationDetail(
        **AdminMonitoringService(get_session_factory()).conversation(
            conversation_id
        )
    )


@router.get("/conversations/{conversation_id}/export")
def export_admin_conversation(
    conversation_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    format: str = Query(default="csv", pattern="^(csv|docx)$"),
) -> Response:
    AuthService.authorize(user, {"admin"})
    from english7.modules.admin.exports import conversation_csv, conversation_docx
    from english7.modules.admin.monitoring import AdminMonitoringService

    conversation = AdminMonitoringService(get_session_factory()).conversation(
        conversation_id
    )
    if format == "docx":
        content = conversation_docx(conversation)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        content = conversation_csv(conversation)
        media_type = "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="conversation-{conversation_id}.{format}"'
            )
        },
    )


@router.get("/decks")
def get_admin_decks(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> dict[str, list[dict[str, Any]]]:
    AuthService.authorize(user, {"admin"})
    from english7.modules.flashcards.repository import (
        SQLAlchemyFlashcardRepository,
    )
    from english7.modules.flashcards.service import FlashcardService

    session_factory = get_session_factory()
    service = FlashcardService(SQLAlchemyFlashcardRepository(session_factory))
    decks = service.list_decks(user.id)
    return {"items": [d.model_dump() for d in decks]}


@router.get("/decks/{deck_id}/cards")
def get_admin_deck_cards(
    deck_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> dict[str, list[dict[str, Any]]]:
    AuthService.authorize(user, {"admin"})
    from english7.modules.flashcards.repository import (
        SQLAlchemyFlashcardRepository,
    )
    from english7.modules.flashcards.service import FlashcardService

    session_factory = get_session_factory()
    service = FlashcardService(SQLAlchemyFlashcardRepository(session_factory))
    cards = service.list_cards(user.id, deck_id)
    return {"items": [c.model_dump() for c in cards]}


def require_admin(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    AuthService.authorize(user, {"admin"})
    return user


AdminUser = Annotated[AuthUser, Depends(require_admin)]


class AdminAuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID
    event_data: dict[str, Any]
    request_id: str | None
    ip_address: str | None
    platform: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    succeeded: bool
    created_at: datetime


def get_admin_audit_service():
    from english7.modules.admin.audit_service import AdminAuditService

    return AdminAuditService(get_session_factory())


@router.get("/audit-events")
def get_admin_audit_events(
    _admin: AdminUser,
    _request: Request,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    service = get_admin_audit_service()
    events = service.list_events(offset=offset, limit=limit)
    return {
        "items": [AdminAuditEventResponse.model_validate(event) for event in events],
        "offset": offset,
        "limit": limit,
        "count": len(events),
    }


def get_admin_speaking_service(
    admin: AdminUser,
) -> SpeakingService:
    from english7.modules.speaking.router import get_speaking_service

    return get_speaking_service()


SpeakingServiceDep = Annotated[SpeakingService, Depends(get_admin_speaking_service)]


@router.get("/speaking/voices")
def get_admin_speaking_voices(
    user: AdminUser,
    service: SpeakingServiceDep,
):
    return service.voices(user.id)


@router.put("/speaking/voice")
def set_admin_speaking_voice(
    payload: VoiceRequest,
    user: AdminUser,
    service: SpeakingServiceDep,
):
    return service.set_voice(user.id, payload.voice_id)


@router.post("/speaking/preview")
def preview_admin_speaking_voice(
    payload: VoiceRequest,
    user: AdminUser,
    service: SpeakingServiceDep,
):
    return Response(
        service.preview(payload.voice_id),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/speaking/attempts/{request_id}")
async def submit_admin_speaking_attempt(
    request_id: UUID,
    card_id: UUID,
    user: AdminUser,
    service: SpeakingServiceDep,
    voice_id: Annotated[str, Query(min_length=1, max_length=100)],
    audio: Annotated[UploadFile, File()],
    prompt: Annotated[str | None, Query(max_length=500)] = None,
):
    try:
        data = await audio.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise ApplicationError("recording_too_large", "Recording exceeds 2 MiB", 413)
        return await run_in_threadpool(
            service.submit, user.id, request_id, card_id, voice_id, data, prompt=prompt
        )
    finally:
        await audio.close()


@router.post("/speaking/attempts/{attempt_id}/audio")
def get_admin_speaking_attempt_audio(
    attempt_id: UUID,
    user: AdminUser,
    service: SpeakingServiceDep,
):
    return Response(
        service.feedback_audio(user.id, attempt_id),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/speaking/history")
def get_admin_speaking_history(
    user: AdminUser,
    service: SpeakingServiceDep,
):
    return {"items": service.history(user.id)}

