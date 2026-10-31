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
from english7.modules.auth.admin_device_service import AdminDeviceService
from english7.modules.auth.router import get_admin_device_service
from english7.modules.admin.dependencies import AdminUser, require_admin
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


class SkillProgress(BaseModel):
    name: str
    key: str
    total_questions: int = 0
    correct_answers: int = 0
    accuracy_percent: int = 0
    status: str = "missing"


class CompetencyStatusItem(BaseModel):
    title: str
    category: str
    score_percent: int = 0
    detail: str
    status: str


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
    mastered_cards: int = 0
    mastery_percent: int = 0
    speaking_count: int = 0
    speaking_avg_score: int = 0
    skills: list[SkillProgress] = Field(default_factory=list)
    mastered_items: list[CompetencyStatusItem] = Field(default_factory=list)
    weak_items: list[CompetencyStatusItem] = Field(default_factory=list)
    missing_items: list[CompetencyStatusItem] = Field(default_factory=list)
    recent_quizzes: list[dict[str, Any]] = Field(default_factory=list)
    recent_speaking: list[dict[str, Any]] = Field(default_factory=list)
    recent_reviews: list[dict[str, Any]] = Field(default_factory=list)


class AdminProgressResponse(BaseModel):
    total_students: int
    total_quizzes: int
    average_accuracy: int
    total_mastered_cards: int = 0
    average_speaking_score: int = 0
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
    from english7.db.models import (
        Activity,
        QuestionSource,
        QuizQuestion,
        Role,
        Section,
        SourceFragment,
        StudentAnswer,
        TestAttempt,
        Unit,
        User,
    )
    from english7.modules.attempts.progress_repository import (
        SQLAlchemyProgressRepository,
    )
    from english7.modules.flashcards.repository import (
        SQLAlchemyFlashcardRepository,
    )
    from english7.modules.flashcards.service import FlashcardService
    from english7.modules.flashcards.models import (
        Flashcard,
        FlashcardReview,
        FlashcardState,
    )
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
            reviewed_cards = card_progress.get("reviewed_cards", 0)
            due_cards = card_progress.get("due_cards", 0)
            difficult_cards = card_progress.get("difficult_cards", 0)

            mastered_cards = (
                session.query(FlashcardState)
                .filter(FlashcardState.user_id == s.id, FlashcardState.successful_reviews > 0)
                .count()
            )
            mastery_percent = (
                round(100 * mastered_cards / reviewed_cards)
                if reviewed_cards > 0
                else 0
            )

            recent_review_rows = (
                session.query(FlashcardReview, Flashcard.word)
                .join(Flashcard, FlashcardReview.card_id == Flashcard.id)
                .filter(FlashcardReview.user_id == s.id)
                .order_by(FlashcardReview.created_at.desc())
                .limit(5)
                .all()
            )
            recent_reviews = [
                {
                    "word": word,
                    "rating": r.result.get("rating", "good") if r.result else "good",
                    "created_at": (
                        r.created_at.isoformat() if r.created_at else None
                    ),
                }
                for r, word in recent_review_rows
            ]

            speaking_attempts = (
                session.query(SpeakingAttempt)
                .filter(SpeakingAttempt.user_id == s.id)
                .order_by(SpeakingAttempt.created_at.desc())
                .all()
            )
            speaking_count = len(speaking_attempts)
            if speaking_count > 0:
                scores = [
                    float(att.result.get("match_percent", 0.0))
                    for att in speaking_attempts
                    if att.result and "match_percent" in att.result
                ]
                speaking_avg_score = (
                    round(sum(scores) / len(scores)) if scores else 0
                )
            else:
                speaking_avg_score = 0

            recent_speaking = [
                {
                    "prompt": att.prompt,
                    "transcript": att.transcript,
                    "match_percent": (
                        round(float(att.result.get("match_percent", 0.0)))
                        if att.result
                        else 0
                    ),
                    "source_label": att.source_label,
                    "created_at": (
                        att.created_at.isoformat() if att.created_at else None
                    ),
                }
                for att in speaking_attempts[:5]
            ]

            # Detailed skills & competencies calculation
            answers_query = (
                session.query(
                    StudentAnswer.is_correct,
                    QuizQuestion.question_type,
                    QuizQuestion.prompt,
                    Unit.number.label("unit_number"),
                    Unit.title.label("unit_title"),
                )
                .join(TestAttempt, StudentAnswer.test_attempt_id == TestAttempt.id)
                .join(QuizQuestion, StudentAnswer.question_id == QuizQuestion.id)
                .outerjoin(QuestionSource, QuizQuestion.id == QuestionSource.question_id)
                .outerjoin(SourceFragment, QuestionSource.source_fragment_id == SourceFragment.id)
                .outerjoin(Activity, SourceFragment.activity_id == Activity.id)
                .outerjoin(Section, Activity.section_id == Section.id)
                .outerjoin(Unit, Section.unit_id == Unit.id)
                .filter(TestAttempt.user_id == s.id, TestAttempt.status == "submitted")
                .all()
            )

            skill_counts = {
                "listening": {"name": "Kỹ năng Nghe (Listening)", "total": 0, "correct": 0},
                "language": {"name": "Ngữ âm & Ngôn ngữ (Language Focus)", "total": 0, "correct": 0},
                "reading": {"name": "Đọc hiểu (Reading)", "total": 0, "correct": 0},
                "writing": {"name": "Kỹ năng Viết (Writing)", "total": 0, "correct": 0},
            }
            unit_stats: dict[int, dict[str, Any]] = {}

            for ans_correct, q_type, q_prompt, u_num, u_title in answers_query:
                is_corr = bool(ans_correct)
                t_lower = (q_type or "").lower()
                p_lower = (q_prompt or "").lower()
                if t_lower == "listening" or "nghe" in p_lower or "listen" in p_lower:
                    s_key = "listening"
                elif t_lower == "reading" or "đoạn văn" in p_lower or "passage" in p_lower or "alaska" in p_lower:
                    s_key = "reading"
                elif t_lower in ("writing", "reorder", "error_correction") or "sắp xếp" in p_lower or "lỗi sai" in p_lower or "/" in p_lower:
                    s_key = "writing"
                else:
                    s_key = "language"

                skill_counts[s_key]["total"] += 1
                if is_corr:
                    skill_counts[s_key]["correct"] += 1

                if u_num is not None:
                    if u_num not in unit_stats:
                        unit_stats[u_num] = {"title": u_title or f"Unit {u_num}", "total": 0, "correct": 0}
                    unit_stats[u_num]["total"] += 1
                    if is_corr:
                        unit_stats[u_num]["correct"] += 1

            skills_data: list[SkillProgress] = []
            for skey in ["listening", "language", "reading", "writing"]:
                info = skill_counts[skey]
                tot = info["total"]
                corr = info["correct"]
                acc = round(100 * corr / tot) if tot > 0 else 0
                if tot == 0:
                    status = "missing"
                elif acc >= 80:
                    status = "mastered"
                elif acc >= 60:
                    status = "passed"
                else:
                    status = "weak"
                skills_data.append(
                    SkillProgress(
                        key=skey,
                        name=info["name"],
                        total_questions=tot,
                        correct_answers=corr,
                        accuracy_percent=acc,
                        status=status,
                    )
                )

            mastered_items: list[CompetencyStatusItem] = []
            weak_items: list[CompetencyStatusItem] = []
            missing_items: list[CompetencyStatusItem] = []

            # Mastered & Weak Skills
            for sk in skills_data:
                if sk.status == "mastered" and sk.total_questions >= 1:
                    mastered_items.append(
                        CompetencyStatusItem(
                            title=sk.name,
                            category="skill",
                            score_percent=sk.accuracy_percent,
                            detail=f"Đúng {sk.correct_answers}/{sk.total_questions} câu ({sk.accuracy_percent}%)",
                            status="mastered",
                        )
                    )
                elif sk.status == "weak":
                    weak_items.append(
                        CompetencyStatusItem(
                            title=sk.name,
                            category="skill",
                            score_percent=sk.accuracy_percent,
                            detail=f"Chỉ đạt {sk.correct_answers}/{sk.total_questions} câu đúng ({sk.accuracy_percent}%) - Cần củng cố",
                            status="weak",
                        )
                    )
                elif sk.status == "missing":
                    missing_items.append(
                        CompetencyStatusItem(
                            title=sk.name,
                            category="skill",
                            score_percent=0,
                            detail="Chưa làm câu hỏi nào thuộc kỹ năng này",
                            status="missing",
                        )
                    )

            # Mastered & Weak Units
            for u_num, u_info in sorted(unit_stats.items()):
                u_tot = u_info["total"]
                u_corr = u_info["correct"]
                u_acc = round(100 * u_corr / u_tot) if u_tot > 0 else 0
                if u_acc >= 80 and u_tot >= 1:
                    mastered_items.append(
                        CompetencyStatusItem(
                            title=f"Unit {u_num}: {u_info['title']}",
                            category="unit",
                            score_percent=u_acc,
                            detail=f"Hoàn thành tốt ({u_corr}/{u_tot} câu đúng - {u_acc}%)",
                            status="mastered",
                        )
                    )
                elif u_acc < 65 and u_tot >= 1:
                    weak_items.append(
                        CompetencyStatusItem(
                            title=f"Unit {u_num}: {u_info['title']}",
                            category="unit",
                            score_percent=u_acc,
                            detail=f"Tỷ lệ đúng thấp ({u_corr}/{u_tot} câu đúng - {u_acc}%)",
                            status="weak",
                        )
                    )

            # Missing Units (Units 1-12)
            for u_num in range(1, 13):
                if u_num not in unit_stats:
                    missing_items.append(
                        CompetencyStatusItem(
                            title=f"Chủ điểm Unit {u_num}",
                            category="unit",
                            score_percent=0,
                            detail="Chưa có lượt làm bài kiểm tra cho Unit này",
                            status="missing",
                        )
                    )

            # Mastered Flashcards
            mastered_card_words = (
                session.query(Flashcard.word)
                .join(FlashcardState, Flashcard.id == FlashcardState.card_id)
                .filter(FlashcardState.user_id == s.id, FlashcardState.successful_reviews >= 2)
                .limit(5)
                .all()
            )
            for (m_word,) in mastered_card_words:
                mastered_items.append(
                    CompetencyStatusItem(
                        title=f"Từ vựng: {m_word}",
                        category="flashcard",
                        score_percent=100,
                        detail="Đã ghi nhớ sâu qua nhiều vòng ôn tập",
                        status="mastered",
                    )
                )

            # Speaking Mastered & Weak
            for att in speaking_attempts:
                if att.result and "match_percent" in att.result:
                    mp = float(att.result["match_percent"])
                    if mp >= 85 and len([i for i in mastered_items if i.category == "speaking"]) < 3:
                        mastered_items.append(
                            CompetencyStatusItem(
                                title=f"Phát âm: \"{att.prompt}\"",
                                category="speaking",
                                score_percent=round(mp),
                                detail=f"Độ chính xác {round(mp)}% - Phát âm chuẩn",
                                status="mastered",
                            )
                        )
                    elif mp < 60 and len([i for i in weak_items if i.category == "speaking"]) < 3:
                        weak_items.append(
                            CompetencyStatusItem(
                                title=f"Phát âm yếu: \"{att.prompt}\"",
                                category="speaking",
                                score_percent=round(mp),
                                detail=f"Độ khớp chỉ đạt {round(mp)}% - Cần luyện lại",
                                status="weak",
                            )
                        )

            # Knowledge Gaps from KnowledgeGapService
            try:
                from english7.modules.knowledge.gap_service import KnowledgeGapService
                gap_analysis = KnowledgeGapService(session_factory).diagnose_gaps(s.id)
                for gap in gap_analysis.gaps[:4]:
                    weak_items.append(
                        CompetencyStatusItem(
                            title=gap.concept_name,
                            category="knowledge_gap",
                            score_percent=round(gap.mastery_score * 100),
                            detail=f"{gap.textbook_citation} (Sai {gap.incorrect_count}/{gap.total_attempts} câu)",
                            status="weak",
                        )
                    )
            except Exception:
                pass

            if reviewed_cards == 0:
                missing_items.append(
                    CompetencyStatusItem(
                        title="Học từ vựng (Flashcard)",
                        category="flashcard",
                        score_percent=0,
                        detail="Chưa bắt đầu ôn tập thẻ từ vựng nào",
                        status="missing",
                    )
                )
            if speaking_count == 0:
                missing_items.append(
                    CompetencyStatusItem(
                        title="Luyện nói & phát âm",
                        category="speaking",
                        score_percent=0,
                        detail="Chưa thực hiện bài luyện nói nào",
                        status="missing",
                    )
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
                    reviewed_cards=reviewed_cards,
                    due_cards=due_cards,
                    difficult_cards=difficult_cards,
                    mastered_cards=mastered_cards,
                    mastery_percent=mastery_percent,
                    speaking_count=speaking_count,
                    speaking_avg_score=speaking_avg_score,
                    skills=skills_data,
                    mastered_items=mastered_items,
                    weak_items=weak_items,
                    missing_items=missing_items,
                    recent_quizzes=recent_quizzes,
                    recent_speaking=recent_speaking,
                    recent_reviews=recent_reviews,
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
    total_mastered = sum(st.mastered_cards for st in students_data)
    speaking_students = [st for st in students_data if st.speaking_count > 0]
    avg_speaking = (
        round(
            sum(st.speaking_avg_score for st in speaking_students)
            / len(speaking_students)
        )
        if speaking_students
        else 0
    )
    return AdminProgressResponse(
        total_students=len(students_data),
        total_quizzes=total_quizzes_all,
        average_accuracy=avg_accuracy,
        total_mastered_cards=total_mastered,
        average_speaking_score=avg_speaking,
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


@router.post("/trusted-devices/revoke-all", status_code=204)
def revoke_admin_trusted_devices(
    admin: AdminUser,
    service: Annotated[AdminDeviceService, Depends(get_admin_device_service)],
) -> Response:
    service.revoke_all(admin.id)
    return Response(status_code=204)


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


from english7.modules.admin.students_router import router as students_router
from english7.modules.admin.dashboard_router import router as dashboard_router
from english7.modules.admin.content_router import router as content_router
from english7.modules.admin.practice_router import router as practice_router

router.include_router(students_router)
router.include_router(dashboard_router)
router.include_router(content_router)
router.include_router(practice_router)

