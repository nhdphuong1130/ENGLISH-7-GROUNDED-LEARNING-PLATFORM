from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, false, or_, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from english7.api.errors import ApplicationError
from english7.core.security import PasswordHasher
from english7.db.models import (
    AudioPlayback,
    AuditEvent,
    ConceptRelationAssertion,
    FragmentConceptAssertion,
    KnowledgeConcept,
    MasteryRecord,
    QuestionSource,
    Quiz,
    QuizQuestion,
    Role,
    SourceFragment,
    StudentAnswer,
    StudentImageUpload,
    TestAttempt,
    TutorChat,
    TutorConversation,
    UnitConceptAssertion,
    User,
)
from english7.modules.flashcards.models import (
    Flashcard,
    FlashcardDeck,
    FlashcardReview,
    FlashcardState,
)
from english7.modules.speaking.models import SpeakingAttempt, SpeakingPreference
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.auth.service import AuthService


@dataclass(frozen=True, slots=True)
class AdminStudent:
    id: UUID
    email: str
    full_name: str | None
    date_of_birth: date | None
    gender: str | None
    school_name: str | None
    class_name: str | None
    is_active: bool
    archived_at: datetime | None

    @property
    def status(self) -> str:
        if self.archived_at is not None:
            return "archived"
        return "active" if self.is_active else "locked"


class AdminStudentService:
    _EDITABLE_FIELDS = {
        "email",
        "full_name",
        "date_of_birth",
        "gender",
        "school_name",
        "class_name",
    }

    def __init__(
        self,
        session_factory: Callable[[], Session],
        password_hasher: PasswordHasher,
        audit_service: AdminAuditService,
    ) -> None:
        self._session_factory = session_factory
        self._password_hasher = password_hasher
        self._audit = audit_service

    @staticmethod
    def _view(user: User) -> AdminStudent:
        return AdminStudent(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            date_of_birth=user.date_of_birth,
            gender=user.gender,
            school_name=user.school_name,
            class_name=user.class_name,
            is_active=user.is_active,
            archived_at=user.archived_at,
        )

    @staticmethod
    def _snapshot(user: User) -> dict[str, Any]:
        return {
            "email": user.email,
            "full_name": user.full_name,
            "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
            "gender": user.gender,
            "school_name": user.school_name,
            "class_name": user.class_name,
            "is_active": user.is_active,
            "archived_at": user.archived_at.isoformat() if user.archived_at else None,
        }

    @staticmethod
    def _normalize_login(value: str) -> str:
        clean = value.strip().lower()
        if "@" in clean:
            return clean
        digits = "".join(character for character in clean if character.isdigit())
        if len(digits) < 9:
            raise ApplicationError(
                "student_login_invalid",
                "Email or phone number is invalid",
                422,
            )
        return AuthService.phone_to_email(digits)

    def _student_query(self):
        return select(User).join(Role, User.role_id == Role.id).where(Role.name == "student")

    def list_students(
        self,
        *,
        query: str | None,
        status: str,
        offset: int,
        limit: int,
    ) -> list[AdminStudent]:
        statement = self._student_query()
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                    User.school_name.ilike(pattern),
                    User.class_name.ilike(pattern),
                )
            )
        if status == "active":
            statement = statement.where(
                User.is_active == true(), User.archived_at.is_(None)
            )
        elif status == "locked":
            statement = statement.where(
                User.is_active == false(), User.archived_at.is_(None)
            )
        elif status == "archived":
            statement = statement.where(User.archived_at.is_not(None))
        statement = statement.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit)
        with self._session_factory() as session:
            return [self._view(user) for user in session.scalars(statement)]

    def get_student(self, student_id: UUID) -> AdminStudent:
        with self._session_factory() as session:
            user = session.scalar(self._student_query().where(User.id == student_id))
            if user is None:
                raise ApplicationError("student_not_found", "Student was not found", 404)
            return self._view(user)

    def create_student(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None,
        school_name: str | None,
        class_name: str | None,
        actor_id: UUID,
        date_of_birth: date | None = None,
        gender: str | None = None,
        **audit_context: Any,
    ) -> AdminStudent:
        login = self._normalize_login(email)
        if len(password) < 8:
            raise ApplicationError("password_too_short", "Password must contain at least 8 characters", 422)
        with self._session_factory() as session:
            if session.scalar(select(User.id).where(User.email == login)) is not None:
                raise ApplicationError("email_already_registered", "Email or phone is already registered", 409)
            role_id = session.scalar(select(Role.id).where(Role.name == "student"))
            if role_id is None:
                raise RuntimeError("Student role is not seeded")
            user = User(
                email=login,
                password_hash=self._password_hasher.hash(password),
                role_id=role_id,
                full_name=full_name.strip() if full_name else None,
                date_of_birth=date_of_birth,
                gender=gender,
                school_name=school_name.strip() if school_name else None,
                class_name=class_name.strip() if class_name else None,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            view = self._view(user)
            after = self._snapshot(user)
        self._record(actor_id, "student.created", view.id, after=after, **audit_context)
        return view

    def update_student(
        self,
        student_id: UUID,
        changes: dict[str, Any],
        *,
        actor_id: UUID,
        **audit_context: Any,
    ) -> AdminStudent:
        invalid = set(changes) - self._EDITABLE_FIELDS
        if invalid:
            raise ApplicationError("student_fields_invalid", "Student contains unsupported fields", 422)
        with self._session_factory() as session:
            user = session.scalar(self._student_query().where(User.id == student_id))
            if user is None:
                raise ApplicationError("student_not_found", "Student was not found", 404)
            before = self._snapshot(user)
            if "email" in changes:
                login = self._normalize_login(str(changes["email"]))
                duplicate = session.scalar(
                    select(User.id).where(User.email == login, User.id != student_id)
                )
                if duplicate is not None:
                    raise ApplicationError("email_already_registered", "Email or phone is already registered", 409)
                changes["email"] = login
            for field, value in changes.items():
                if isinstance(value, str) and field not in {"email", "gender"}:
                    value = value.strip() or None
                setattr(user, field, value)
            session.commit()
            session.refresh(user)
            view = self._view(user)
            after = self._snapshot(user)
        self._record(actor_id, "student.updated", student_id, before=before, after=after, **audit_context)
        return view

    def reset_password(
        self,
        student_id: UUID,
        new_password: str,
        *,
        actor_id: UUID,
        **audit_context: Any,
    ) -> None:
        if len(new_password) < 8:
            raise ApplicationError("password_too_short", "Password must contain at least 8 characters", 422)
        with self._session_factory() as session:
            user = session.scalar(self._student_query().where(User.id == student_id))
            if user is None:
                raise ApplicationError("student_not_found", "Student was not found", 404)
            user.password_hash = self._password_hasher.hash(new_password)
            session.commit()
        self._record(actor_id, "student.password_reset", student_id, after={"password": new_password}, **audit_context)

    def set_locked(
        self,
        student_id: UUID,
        locked: bool,
        *,
        actor_id: UUID,
        **audit_context: Any,
    ) -> AdminStudent:
        action = "student.locked" if locked else "student.unlocked"
        return self._set_state(student_id, actor_id=actor_id, action=action, is_active=not locked, **audit_context)

    def archive(self, student_id: UUID, *, actor_id: UUID, **audit_context: Any) -> AdminStudent:
        return self._set_state(
            student_id,
            actor_id=actor_id,
            action="student.archived",
            is_active=False,
            archived_at=datetime.now(timezone.utc),
            **audit_context,
        )

    def restore(self, student_id: UUID, *, actor_id: UUID, **audit_context: Any) -> AdminStudent:
        return self._set_state(
            student_id,
            actor_id=actor_id,
            action="student.restored",
            is_active=True,
            archived_at=None,
            **audit_context,
        )

    def _set_state(
        self,
        student_id: UUID,
        *,
        actor_id: UUID,
        action: str,
        is_active: bool,
        archived_at: datetime | None | object = ...,
        **audit_context: Any,
    ) -> AdminStudent:
        with self._session_factory() as session:
            user = session.scalar(self._student_query().where(User.id == student_id))
            if user is None:
                raise ApplicationError("student_not_found", "Student was not found", 404)
            before = self._snapshot(user)
            user.is_active = is_active
            if archived_at is not ...:
                user.archived_at = archived_at  # type: ignore[assignment]
            session.commit()
            session.refresh(user)
            view = self._view(user)
            after = self._snapshot(user)
        self._record(actor_id, action, student_id, before=before, after=after, **audit_context)
        return view

    def delete_student(
        self,
        student_id: UUID,
        *,
        confirmation: str,
        actor_id: UUID,
        **audit_context: Any,
    ) -> None:
        if student_id == actor_id:
            raise ApplicationError("admin_self_delete_forbidden", "Admin cannot delete their own account", 409)
        with self._session_factory() as session:
            user = session.scalar(self._student_query().where(User.id == student_id))
            if user is None:
                raise ApplicationError("student_not_found", "Student was not found", 404)
            if confirmation.strip().casefold() != user.email.casefold():
                raise ApplicationError("confirmation_mismatch", "Confirmation does not match the student login", 422)
            before = self._snapshot(user)
            self._delete_related_data(session, student_id)
            session.delete(user)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise ApplicationError(
                    "student_has_related_data",
                    "Archive this student because related learning data must be retained",
                    409,
                ) from error
        self._record(actor_id, "student.deleted", student_id, before=before, **audit_context)

    @staticmethod
    def _delete_related_data(session: Session, student_id: UUID) -> None:
        personal_deck_ids = list(
            session.scalars(
                select(FlashcardDeck.id).where(FlashcardDeck.owner_id == student_id)
            )
        )
        personal_card_ids = (
            list(
                session.scalars(
                    select(Flashcard.id).where(Flashcard.deck_id.in_(personal_deck_ids))
                )
            )
            if personal_deck_ids
            else []
        )
        card_state_filter = FlashcardState.user_id == student_id
        card_review_filter = FlashcardReview.user_id == student_id
        if personal_card_ids:
            card_state_filter = or_(
                card_state_filter,
                FlashcardState.card_id.in_(personal_card_ids),
            )
            card_review_filter = or_(
                card_review_filter,
                FlashcardReview.card_id.in_(personal_card_ids),
            )
        session.execute(delete(FlashcardState).where(card_state_filter))
        session.execute(delete(FlashcardReview).where(card_review_filter))
        session.execute(delete(SpeakingAttempt).where(SpeakingAttempt.user_id == student_id))
        session.execute(delete(SpeakingPreference).where(SpeakingPreference.user_id == student_id))
        if personal_card_ids:
            session.execute(delete(Flashcard).where(Flashcard.id.in_(personal_card_ids)))
        if personal_deck_ids:
            session.execute(delete(FlashcardDeck).where(FlashcardDeck.id.in_(personal_deck_ids)))

        owned_quiz_ids = list(
            session.scalars(
                select(Quiz.id).where(Quiz.created_for_user_id == student_id)
            )
        )
        attempt_filter = TestAttempt.user_id == student_id
        if owned_quiz_ids:
            attempt_filter = or_(attempt_filter, TestAttempt.quiz_id.in_(owned_quiz_ids))
        attempt_ids = list(session.scalars(select(TestAttempt.id).where(attempt_filter)))
        question_ids = (
            list(
                session.scalars(
                    select(QuizQuestion.id).where(
                        QuizQuestion.quiz_id.in_(owned_quiz_ids)
                    )
                )
            )
            if owned_quiz_ids
            else []
        )
        if attempt_ids:
            session.execute(
                delete(AudioPlayback).where(
                    AudioPlayback.test_attempt_id.in_(attempt_ids)
                )
            )
        answer_filter = None
        if attempt_ids:
            answer_filter = StudentAnswer.test_attempt_id.in_(attempt_ids)
        if question_ids:
            by_question = StudentAnswer.question_id.in_(question_ids)
            answer_filter = (
                by_question if answer_filter is None else or_(answer_filter, by_question)
            )
        if answer_filter is not None:
            session.execute(delete(StudentAnswer).where(answer_filter))
        if attempt_ids:
            session.execute(delete(TestAttempt).where(TestAttempt.id.in_(attempt_ids)))
        if question_ids:
            session.execute(
                delete(QuestionSource).where(
                    QuestionSource.question_id.in_(question_ids)
                )
            )
            session.execute(delete(QuizQuestion).where(QuizQuestion.id.in_(question_ids)))
        if owned_quiz_ids:
            session.execute(delete(Quiz).where(Quiz.id.in_(owned_quiz_ids)))

        session.execute(delete(TutorChat).where(TutorChat.user_id == student_id))
        session.execute(
            delete(TutorConversation).where(TutorConversation.user_id == student_id)
        )
        session.execute(
            delete(StudentImageUpload).where(StudentImageUpload.owner_id == student_id)
        )
        session.execute(delete(MasteryRecord).where(MasteryRecord.user_id == student_id))

        for model in (
            SourceFragment,
            KnowledgeConcept,
            FragmentConceptAssertion,
            ConceptRelationAssertion,
            UnitConceptAssertion,
        ):
            session.execute(
                update(model)
                .where(model.reviewer_id == student_id)
                .values(reviewer_id=None)
            )
        session.execute(
            update(AuditEvent)
            .where(AuditEvent.actor_id == student_id)
            .values(actor_id=None)
        )

    def _record(
        self,
        actor_id: UUID,
        action: str,
        student_id: UUID,
        *,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
    ) -> None:
        self._audit.record(
            actor_id=actor_id,
            action=action,
            entity_type="user",
            entity_id=student_id,
            before=before,
            after=after,
            request_id=request_id,
            ip_address=ip_address,
            platform=platform,
        )
