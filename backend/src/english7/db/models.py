from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Unicode,
    UnicodeText,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from english7.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    REJECTED = "rejected"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EXPIRED = "expired"


class ImageUploadStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Role(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="vi")
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Unicode(255))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(30))
    school_name: Mapped[str | None] = mapped_column(Unicode(255))
    class_name: Mapped[str | None] = mapped_column(Unicode(100))

    role: Mapped[Role] = relationship()


class Textbook(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "textbooks"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    edition: Mapped[str | None] = mapped_column(String(100))
    publisher: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Unit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("textbook_id", "number"),)

    textbook_id: Mapped[UUID] = mapped_column(ForeignKey("textbooks.id"))
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Section(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("unit_id", "position"),)

    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_type: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class Activity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "activities"

    section_id: Mapped[UUID] = mapped_column(ForeignKey("sections.id"))
    number: Mapped[str | None] = mapped_column(String(30))
    activity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    instruction: Mapped[str | None] = mapped_column(UnicodeText)


class SourceDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_documents"

    textbook_id: Mapped[UUID | None] = mapped_column(ForeignKey("textbooks.id"))
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ingestion_version: Mapped[str] = mapped_column(String(100), nullable=False)


class SourceFragment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_fragments"
    __table_args__ = (
        CheckConstraint("pdf_page >= 0"),
        CheckConstraint("printed_page IS NULL OR printed_page >= 0"),
        CheckConstraint("x >= 0 AND y >= 0 AND width >= 0 AND height >= 0"),
    )

    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_documents.id"),
        nullable=False,
    )
    activity_id: Mapped[UUID | None] = mapped_column(ForeignKey("activities.id"))
    pdf_page: Mapped[int] = mapped_column(Integer, nullable=False)
    printed_page: Mapped[int | None] = mapped_column(Integer)
    region_type: Mapped[str] = mapped_column(String(80), default="text")
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(UnicodeText)
    normalized_text: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    detection_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    detector_version: Mapped[str | None] = mapped_column(String(100))
    ocr_version: Mapped[str | None] = mapped_column(String(100))
    review_status: Mapped[str] = mapped_column(
        String(30),
        default=ReviewStatus.DRAFT,
        nullable=False,
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @validates("pdf_page", "printed_page", "x", "y", "width", "height")
    def validate_non_negative(self, key: str, value: float | int | None):
        if value is not None and value < 0:
            raise ValueError(f"{key} must not be negative")
        return value

    def publish(self) -> None:
        if self.review_status != ReviewStatus.VERIFIED:
            raise ValueError("Only verified source fragments can be published")
        self.is_published = True


class MediaAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "media_assets"

    object_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)


class StudentImageUpload(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "student_image_uploads"
    __table_args__ = (
        CheckConstraint("size_bytes > 0"),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)"
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=ImageUploadStatus.QUEUED, nullable=False
    )
    ocr_text: Mapped[str | None] = mapped_column(UnicodeText)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column()


class AudioTrack(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audio_tracks"

    activity_id: Mapped[UUID] = mapped_column(ForeignKey("activities.id"))
    media_asset_id: Mapped[UUID] = mapped_column(ForeignKey("media_assets.id"))
    transcript_fragment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_fragments.id")
    )
    track_number: Mapped[int] = mapped_column(Integer, nullable=False)


class QuizBlueprint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quiz_blueprints"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Quiz(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quizzes"

    blueprint_id: Mapped[UUID] = mapped_column(ForeignKey("quiz_blueprints.id"))
    created_for_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class QuizQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quiz_questions"

    quiz_id: Mapped[UUID] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    prompt: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    question_type: Mapped[str] = mapped_column(String(80), default="multiple_choice")
    answer_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source_links: Mapped[list[QuestionSource]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )

    def publish(self) -> None:
        if not self.source_links:
            raise ValueError("A quiz question requires at least one source")
        self.is_published = True


class QuestionSource(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "question_sources"
    __table_args__ = (UniqueConstraint("question_id", "source_fragment_id"),)

    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("quiz_questions.id"),
        nullable=False,
    )
    source_fragment_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_fragments.id"),
        nullable=False,
    )

    question: Mapped[QuizQuestion] = relationship(back_populates="source_links")


class TestAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "test_attempts"

    quiz_id: Mapped[UUID] = mapped_column(ForeignKey("quizzes.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(
        String(30),
        default=AttemptStatus.IN_PROGRESS,
        nullable=False,
    )


class AudioPlayback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audio_playbacks"
    __table_args__ = (
        UniqueConstraint("test_attempt_id", "audio_track_id"),
        CheckConstraint("remaining_plays >= 0"),
    )

    test_attempt_id: Mapped[UUID] = mapped_column(ForeignKey("test_attempts.id"))
    audio_track_id: Mapped[UUID] = mapped_column(ForeignKey("audio_tracks.id"))
    remaining_plays: Mapped[int] = mapped_column(Integer, nullable=False)

    def consume_play(self) -> None:
        if self.remaining_plays <= 0:
            raise ValueError("No audio plays remaining")
        self.remaining_plays -= 1


class StudentAnswer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "student_answers"
    __table_args__ = (UniqueConstraint("test_attempt_id", "question_id"),)

    test_attempt_id: Mapped[UUID] = mapped_column(ForeignKey("test_attempts.id"))
    question_id: Mapped[UUID] = mapped_column(ForeignKey("quiz_questions.id"))
    answer_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)


class MasteryRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "mastery_records"
    __table_args__ = (UniqueConstraint("user_id", "concept_key"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    concept_key: Mapped[str] = mapped_column(String(255), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class KnowledgeConcept(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_concepts"
    __table_args__ = (
        UniqueConstraint(
            "ontology_version",
            "concept_type",
            "canonical_name",
            name="uq_knowledge_concept_identity",
        ),
    )

    concept_type: Mapped[str] = mapped_column(String(50), nullable=False)
    canonical_name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    description_en: Mapped[str | None] = mapped_column(UnicodeText)
    description_vi: Mapped[str | None] = mapped_column(UnicodeText)
    concept_text: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    ontology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    concept_properties: Mapped[dict[str, Any]] = mapped_column(
        "properties", JSON, default=dict, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255))
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()


class _ScoredAssertion:
    role_weight: Mapped[float]
    confidence: Mapped[float]

    def validate_scores(self) -> None:
        for field in ("role_weight", "confidence"):
            value = getattr(self, field)
            if not 0 <= value <= 1:
                raise ValueError(f"{field} must be between zero and one")


class FragmentConceptAssertion(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, _ScoredAssertion
):
    __tablename__ = "fragment_concept_assertions"
    __table_args__ = (
        UniqueConstraint(
            "fragment_id",
            "concept_id",
            "assertion_type",
            name="uq_fragment_concept_assertion",
        ),
        CheckConstraint(
            "role_weight >= 0 AND role_weight <= 1",
            name="ck_fragment_concept_role_weight",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_fragment_concept_confidence",
        ),
    )

    fragment_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_fragments.id"), nullable=False
    )
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id"), nullable=False
    )
    assertion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    role_weight: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(1024))
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255))
    ontology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()


class ConceptRelationAssertion(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, _ScoredAssertion
):
    __tablename__ = "concept_relation_assertions"
    __table_args__ = (
        UniqueConstraint(
            "source_concept_id",
            "target_concept_id",
            "assertion_type",
            name="uq_concept_relation_assertion",
        ),
        CheckConstraint(
            "role_weight >= 0 AND role_weight <= 1",
            name="ck_concept_relation_role_weight",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_concept_relation_confidence",
        ),
    )

    source_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id"), nullable=False
    )
    target_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id"), nullable=False
    )
    assertion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    role_weight: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_fragment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_fragments.id")
    )
    evidence_reference: Mapped[str | None] = mapped_column(String(1024))
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255))
    ontology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()


class UnitConceptAssertion(Base, UUIDPrimaryKeyMixin, TimestampMixin, _ScoredAssertion):
    __tablename__ = "unit_concept_assertions"
    __table_args__ = (
        UniqueConstraint(
            "unit_id",
            "concept_id",
            "assertion_type",
            name="uq_unit_concept_assertion",
        ),
        CheckConstraint(
            "role_weight >= 0 AND role_weight <= 1",
            name="ck_unit_concept_role_weight",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_unit_concept_confidence",
        ),
    )

    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"), nullable=False)
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id"), nullable=False
    )
    assertion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    role_weight: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_fragment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_fragments.id")
    )
    evidence_reference: Mapped[str | None] = mapped_column(String(1024))
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255))
    ontology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()


class GraphBuild(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_builds"
    __table_args__ = (
        CheckConstraint(
            "embedding_dimensions > 0", name="ck_graph_build_embedding_dimensions"
        ),
    )

    source_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    ontology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_query_prefix: Mapped[str] = mapped_column(Unicode(1024), nullable=False)
    embedding_passage_prefix: Mapped[str] = mapped_column(
        Unicode(1024), nullable=False
    )
    embedding_preprocessing_version: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    fragment_index_name: Mapped[str | None] = mapped_column(String(255))
    concept_index_name: Mapped[str | None] = mapped_column(String(255))
    expected_counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    actual_counts: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column()
    activated_at: Mapped[datetime | None] = mapped_column()


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))


class AuditEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_events"

    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class TutorConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_conversations"
    __table_args__ = (
        Index(
            "ix_tutor_conversations_owner_updated",
            "user_id",
            "updated_at",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Unicode(160), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    addressing_preference: Mapped[str | None] = mapped_column(Unicode(120))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped[User] = relationship()
    exchanges: Mapped[list[TutorChat]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TutorChat.sequence_number",
    )


class TutorChat(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_chats"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence_number",
            name="uq_tutor_chats_conversation_sequence",
        ),
        Index(
            "ix_tutor_chats_conversation_sequence",
            "conversation_id",
            "sequence_number",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("tutor_conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    answer: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    upload_id: Mapped[UUID | None] = mapped_column(ForeignKey("student_image_uploads.id"), nullable=True)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    user: Mapped[User] = relationship()
    conversation: Mapped[TutorConversation] = relationship(
        back_populates="exchanges"
    )


# Register feature-owned models in the shared metadata for migrations/tests.
from english7.modules.flashcards import models as _flashcard_models  # noqa: E402,F401
from english7.modules.speaking import models as _speaking_models  # noqa: E402,F401
