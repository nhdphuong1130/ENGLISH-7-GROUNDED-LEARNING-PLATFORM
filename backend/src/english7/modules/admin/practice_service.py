from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from english7.api.errors import ApplicationError
from english7.db.models import (
    Activity,
    ContentRevision,
    QuestionSource,
    Quiz,
    QuizBlueprint,
    QuizQuestion,
    ReviewStatus,
    Section,
    SourceFragment,
    StudentAnswer,
    Unit,
)
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.ai.contracts import AIProviderError
from english7.modules.flashcards.domain import normalize_word
from english7.modules.flashcards.models import Flashcard, FlashcardDeck, FlashcardReview, FlashcardState
from english7.modules.speaking.models import SpeakingAttempt


class PronunciationProvider(Protocol):
    def pronounce(self, text: str) -> str: ...


class AdminPracticeService:
    def __init__(self, session_factory: Callable[[], Session], audit_service: AdminAuditService, pronunciation_provider: PronunciationProvider | None = None) -> None:
        self._session_factory = session_factory
        self._audit = audit_service
        self._pronunciation_provider = pronunciation_provider

    @staticmethod
    def _blueprint_snapshot(row: QuizBlueprint) -> dict[str, Any]:
        return {"name": row.name, "duration_minutes": row.duration_minutes, "difficulty": row.difficulty, "policy": row.policy, "is_active": row.is_active}

    @staticmethod
    def _deck_snapshot(row: FlashcardDeck) -> dict[str, Any]:
        return {"name": row.name, "kind": row.kind, "unit_id": str(row.unit_id) if row.unit_id else None, "unit_number": row.unit_number, "is_active": row.is_active}

    @staticmethod
    def _card_snapshot(row: Flashcard) -> dict[str, Any]:
        return {
            "deck_id": str(row.deck_id), "word": row.word, "meaning": row.meaning,
            "example": row.example, "notes": row.notes, "ipa": row.ipa, "pos": row.pos,
            "source_fragment_id": str(row.source_fragment_id) if row.source_fragment_id else None,
            "unit_number": row.unit_number, "page": row.page, "is_published": row.is_published,
        }

    @staticmethod
    def _question_snapshot(row: QuizQuestion, source_ids: list[UUID]) -> dict[str, Any]:
        return {"quiz_id": str(row.quiz_id), "prompt": row.prompt, "question_type": row.question_type, "answer_payload": row.answer_payload, "source_fragment_ids": [str(item) for item in source_ids], "is_published": row.is_published}

    @staticmethod
    def _current_version(session: Session, entity_type: str, entity_id: UUID) -> int:
        return session.scalar(select(func.max(ContentRevision.version)).where(ContentRevision.entity_type == entity_type, ContentRevision.entity_id == entity_id)) or 0

    def _revision(self, session: Session, entity_type: str, entity_id: UUID, snapshot: dict[str, Any], actor_id: UUID, status: str) -> int:
        version = self._current_version(session, entity_type, entity_id) + 1
        session.add(ContentRevision(entity_type=entity_type, entity_id=entity_id, version=version, status=status, snapshot=snapshot, actor_id=actor_id, published_at=datetime.now(timezone.utc) if status == "published" else None))
        return version

    def _ensure_version(self, session: Session, entity_type: str, entity_id: UUID, expected: int) -> None:
        actual = self._current_version(session, entity_type, entity_id)
        if expected != actual:
            raise ApplicationError("content_version_conflict", "Content changed on another device; reload before saving", 409, {"expected": expected, "actual": actual})

    def _record(self, actor_id: UUID, action: str, entity_id: UUID, before=None, after=None, **context: Any) -> None:
        self._audit.record(actor_id=actor_id, action=action, entity_type=action.split(".", 1)[0], entity_id=entity_id, before=before, after=after, request_id=context.get("request_id"), ip_address=context.get("ip_address"), platform=context.get("platform"))

    def create_blueprint(self, *, name: str, duration_minutes: int, difficulty: str, policy: dict[str, Any], actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            row = QuizBlueprint(name=name.strip(), duration_minutes=duration_minutes, difficulty=difficulty, policy=policy, is_active=False)
            session.add(row); session.flush()
            snapshot = self._blueprint_snapshot(row)
            version = self._revision(session, "quiz_blueprint", row.id, snapshot, actor_id, "draft")
            session.commit(); row_id = row.id
        result = {"id": row_id, **snapshot, "version": version, "status": "draft"}
        self._record(actor_id, "quiz_blueprint.created", row_id, after=result, **context)
        return result

    def list_blueprints(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = list(session.scalars(select(QuizBlueprint).order_by(QuizBlueprint.name)))
            return [self._view(session, "quiz_blueprint", row.id, self._blueprint_snapshot(row)) for row in rows]

    def update_blueprint(self, blueprint_id: UUID, changes: dict[str, Any], *, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        allowed = {"name", "duration_minutes", "difficulty", "policy"}
        if set(changes) - allowed:
            raise ApplicationError("practice_fields_invalid", "Blueprint contains unsupported fields", 422)
        with self._session_factory() as session:
            row = session.get(QuizBlueprint, blueprint_id)
            if row is None: raise ApplicationError("blueprint_not_found", "Quiz blueprint was not found", 404)
            self._ensure_version(session, "quiz_blueprint", blueprint_id, expected_version); before = self._blueprint_snapshot(row)
            for field, value in changes.items(): setattr(row, field, value.strip() if isinstance(value, str) else value)
            row.is_active = False; snapshot = self._blueprint_snapshot(row)
            version = self._revision(session, "quiz_blueprint", row.id, snapshot, actor_id, "draft"); session.commit()
        result = {"id": blueprint_id, **snapshot, "version": version, "status": "draft"}; self._record(actor_id, "quiz_blueprint.updated", blueprint_id, before, result, **context); return result

    def set_blueprint_status(self, blueprint_id: UUID, *, expected_version: int, active: bool, actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(QuizBlueprint, blueprint_id)
            if row is None: raise ApplicationError("blueprint_not_found", "Quiz blueprint was not found", 404)
            self._ensure_version(session, "quiz_blueprint", blueprint_id, expected_version); before = self._blueprint_snapshot(row)
            row.is_active = active; snapshot = self._blueprint_snapshot(row); status = "published" if active else "archived"
            version = self._revision(session, "quiz_blueprint", row.id, snapshot, actor_id, status); session.commit()
        result = {"id": blueprint_id, **snapshot, "version": version, "status": status}; self._record(actor_id, f"quiz_blueprint.{status}", blueprint_id, before, result, **context); return result

    def delete_blueprint(self, blueprint_id: UUID, *, actor_id: UUID, **context: Any) -> None:
        with self._session_factory() as session:
            row = session.get(QuizBlueprint, blueprint_id)
            if row is None: raise ApplicationError("blueprint_not_found", "Quiz blueprint was not found", 404)
            if session.scalar(select(Quiz.id).where(Quiz.blueprint_id == blueprint_id).limit(1)) is not None: raise ApplicationError("practice_content_in_use", "Archive practice content that has learner data", 409)
            before = self._blueprint_snapshot(row); session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "quiz_blueprint", ContentRevision.entity_id == blueprint_id)); session.delete(row); session.commit()
        self._record(actor_id, "quiz_blueprint.deleted", blueprint_id, before=before, **context)

    def create_deck(self, *, name: str, unit_id: UUID, actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            unit = session.get(Unit, unit_id)
            if unit is None: raise ApplicationError("unit_not_found", "Unit was not found", 404)
            if session.scalar(select(FlashcardDeck.id).where(FlashcardDeck.kind == "textbook", FlashcardDeck.unit_id == unit_id)) is not None: raise ApplicationError("deck_conflict", "This unit already has a textbook deck", 409)
            row = FlashcardDeck(owner_id=None, name=name.strip(), kind="textbook", unit_id=unit_id, unit_number=unit.number, is_active=False)
            session.add(row); session.flush(); snapshot = self._deck_snapshot(row); version = self._revision(session, "flashcard_deck", row.id, snapshot, actor_id, "draft"); session.commit(); row_id = row.id
        result = {"id": row_id, **snapshot, "version": version, "status": "draft"}; self._record(actor_id, "flashcard_deck.created", row_id, after=result, **context); return result

    def list_decks(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = list(session.scalars(select(FlashcardDeck).where(FlashcardDeck.kind == "textbook").order_by(FlashcardDeck.unit_number)))
            return [
                {
                    **self._view(
                        session, "flashcard_deck", row.id, self._deck_snapshot(row)
                    ),
                    "child_count": session.scalar(
                        select(func.count()).select_from(Flashcard).where(
                            Flashcard.deck_id == row.id
                        )
                    ) or 0,
                }
                for row in rows
            ]

    def update_deck(self, deck_id: UUID, *, name: str, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(FlashcardDeck, deck_id)
            if row is None or row.kind != "textbook": raise ApplicationError("deck_not_found", "Textbook deck was not found", 404)
            self._ensure_version(session, "flashcard_deck", deck_id, expected_version); before = self._deck_snapshot(row); row.name = name.strip(); row.is_active = False; snapshot = self._deck_snapshot(row); version = self._revision(session, "flashcard_deck", row.id, snapshot, actor_id, "draft"); session.commit()
        result = {"id": deck_id, **snapshot, "version": version, "status": "draft"}; self._record(actor_id, "flashcard_deck.updated", deck_id, before, result, **context); return result

    def delete_deck(self, deck_id: UUID, *, actor_id: UUID, **context: Any) -> None:
        with self._session_factory() as session:
            row = session.get(FlashcardDeck, deck_id)
            if row is None or row.kind != "textbook": raise ApplicationError("deck_not_found", "Textbook deck was not found", 404)
            if session.scalar(select(Flashcard.id).where(Flashcard.deck_id == deck_id).limit(1)) is not None: raise ApplicationError("practice_content_in_use", "Archive a deck that contains cards", 409)
            before = self._deck_snapshot(row); session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "flashcard_deck", ContentRevision.entity_id == deck_id)); session.delete(row); session.commit()
        self._record(actor_id, "flashcard_deck.deleted", deck_id, before=before, **context)

    def set_deck_status(self, deck_id: UUID, *, expected_version: int, active: bool, actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(FlashcardDeck, deck_id)
            if row is None or row.kind != "textbook": raise ApplicationError("deck_not_found", "Textbook deck was not found", 404)
            self._ensure_version(session, "flashcard_deck", deck_id, expected_version); before = self._deck_snapshot(row); row.is_active = active; snapshot = self._deck_snapshot(row); status = "published" if active else "archived"; version = self._revision(session, "flashcard_deck", row.id, snapshot, actor_id, status); session.commit()
        result = {"id": deck_id, **snapshot, "version": version, "status": status}; self._record(actor_id, f"flashcard_deck.{status}", deck_id, before, result, **context); return result

    def create_card(self, deck_id: UUID, *, word: str, meaning: str, source_fragment_id: UUID, actor_id: UUID, example: str = "", notes: str = "", pos: str | None = None, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            deck = session.get(FlashcardDeck, deck_id)
            if deck is None or deck.kind != "textbook": raise ApplicationError("deck_not_found", "Textbook deck was not found", 404)
            fragment = session.get(SourceFragment, source_fragment_id)
            if fragment is None or fragment.review_status != ReviewStatus.VERIFIED or not fragment.is_published or fragment.printed_page is None: raise ApplicationError("grounding_required", "A verified published textbook page is required", 422)
            unit_number = session.scalar(select(Unit.number).join(Section, Section.unit_id == Unit.id).join(Activity, Activity.section_id == Section.id).where(Activity.id == fragment.activity_id))
            if unit_number != deck.unit_number: raise ApplicationError("grounding_required", "Card source must belong to the deck unit", 422)
            ipa = self._pronounce(word)
            row = Flashcard(deck_id=deck_id, word=word.strip(), normalized_word=normalize_word(word), meaning=meaning.strip(), example=example.strip(), notes=notes.strip(), ipa=ipa, pos=pos, source_fragment_id=source_fragment_id, unit_number=unit_number, page=fragment.printed_page, is_published=False)
            session.add(row); session.flush(); snapshot = self._card_snapshot(row); version = self._revision(session, "flashcard", row.id, snapshot, actor_id, "draft"); session.commit(); row_id = row.id
        result = {"id": row_id, **snapshot, "version": version, "status": "draft"}; self._record(actor_id, "flashcard.created", row_id, after=result, **context); return result

    def list_cards(self, deck_id: UUID) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = list(session.scalars(select(Flashcard).where(Flashcard.deck_id == deck_id).order_by(Flashcard.word)))
            return [self._view(session, "flashcard", row.id, self._card_snapshot(row)) for row in rows]

    def list_speaking_prompts(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = list(session.scalars(select(Flashcard).join(FlashcardDeck, Flashcard.deck_id == FlashcardDeck.id).where(FlashcardDeck.kind == "textbook").order_by(Flashcard.unit_number, Flashcard.word)))
            return [self._view(session, "flashcard", row.id, self._card_snapshot(row)) for row in rows]

    def update_card(self, card_id: UUID, changes: dict[str, Any], *, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        allowed = {"word", "meaning", "example", "notes", "pos", "source_fragment_id"}
        if set(changes) - allowed: raise ApplicationError("practice_fields_invalid", "Flashcard contains unsupported fields", 422)
        with self._session_factory() as session:
            row = session.get(Flashcard, card_id)
            if row is None: raise ApplicationError("card_not_found", "Flashcard was not found", 404)
            self._ensure_version(session, "flashcard", card_id, expected_version); before = self._card_snapshot(row)
            if "source_fragment_id" in changes:
                fragment = session.get(SourceFragment, changes["source_fragment_id"])
                if fragment is None or fragment.review_status != ReviewStatus.VERIFIED or not fragment.is_published or fragment.printed_page is None: raise ApplicationError("grounding_required", "A verified published textbook page is required", 422)
                row.source_fragment_id = fragment.id; row.page = fragment.printed_page
            for field in allowed - {"source_fragment_id"}:
                if field in changes: setattr(row, field, changes[field].strip() if isinstance(changes[field], str) else changes[field])
            if "word" in changes:
                row.normalized_word = normalize_word(row.word); generated = self._pronounce(row.word)
                if generated: row.ipa = generated
            row.is_published = False; snapshot = self._card_snapshot(row); version = self._revision(session, "flashcard", row.id, snapshot, actor_id, "draft"); session.commit()
        result = {"id": card_id, **snapshot, "version": version, "status": "draft"}; self._record(actor_id, "flashcard.updated", card_id, before, result, **context); return result

    def delete_card(self, card_id: UUID, *, actor_id: UUID, **context: Any) -> None:
        with self._session_factory() as session:
            row = session.get(Flashcard, card_id)
            if row is None: raise ApplicationError("card_not_found", "Flashcard was not found", 404)
            used = session.scalar(select(FlashcardState.id).where(FlashcardState.card_id == card_id).limit(1)) or session.scalar(select(FlashcardReview.id).where(FlashcardReview.card_id == card_id).limit(1)) or session.scalar(select(SpeakingAttempt.id).where(SpeakingAttempt.card_id == card_id).limit(1))
            if used is not None: raise ApplicationError("practice_content_in_use", "Archive practice content that has learner data", 409)
            before = self._card_snapshot(row); session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "flashcard", ContentRevision.entity_id == card_id)); session.delete(row); session.commit()
        self._record(actor_id, "flashcard.deleted", card_id, before=before, **context)

    def publish_card(self, card_id: UUID, *, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        return self._set_card_status(card_id, expected_version=expected_version, published=True, actor_id=actor_id, **context)

    def archive_card(self, card_id: UUID, *, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        return self._set_card_status(card_id, expected_version=expected_version, published=False, actor_id=actor_id, **context)

    def _set_card_status(self, card_id: UUID, *, expected_version: int, published: bool, actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(Flashcard, card_id)
            if row is None: raise ApplicationError("card_not_found", "Flashcard was not found", 404)
            self._ensure_version(session, "flashcard", card_id, expected_version)
            fragment = session.get(SourceFragment, row.source_fragment_id) if row.source_fragment_id else None
            if published and (fragment is None or fragment.review_status != ReviewStatus.VERIFIED or not fragment.is_published or fragment.printed_page is None): raise ApplicationError("grounding_required", "A verified published textbook page is required", 422)
            before = self._card_snapshot(row); row.is_published = published; snapshot = self._card_snapshot(row); status = "published" if published else "archived"; version = self._revision(session, "flashcard", row.id, snapshot, actor_id, status); session.commit()
        result = {"id": card_id, **snapshot, "version": version, "status": status}; self._record(actor_id, f"flashcard.{status}", card_id, before, result, **context); return result

    def create_question(self, *, quiz_id: UUID, prompt: str, question_type: str, answer_payload: dict[str, Any], source_fragment_ids: list[UUID], actor_id: UUID, **context: Any) -> dict[str, Any]:
        self._validate_answer(question_type, answer_payload)
        with self._session_factory() as session:
            if session.get(Quiz, quiz_id) is None: raise ApplicationError("quiz_not_found", "Quiz was not found", 404)
            row = QuizQuestion(quiz_id=quiz_id, prompt=prompt.strip(), question_type=question_type, answer_payload=answer_payload, is_published=False); session.add(row); session.flush()
            for source_id in source_fragment_ids:
                if session.get(SourceFragment, source_id) is None: raise ApplicationError("fragment_not_found", "Source fragment was not found", 404)
                session.add(QuestionSource(question_id=row.id, source_fragment_id=source_id))
            snapshot = self._question_snapshot(row, source_fragment_ids); version = self._revision(session, "quiz_question", row.id, snapshot, actor_id, "draft"); session.commit(); row_id = row.id
        result = {"id": row_id, **snapshot, "version": version, "status": "draft"}; self._record(actor_id, "quiz_question.created", row_id, after=result, **context); return result

    def list_questions(self, quiz_id: UUID | None = None) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            query = select(QuizQuestion).order_by(QuizQuestion.created_at.desc())
            if quiz_id is not None: query = query.where(QuizQuestion.quiz_id == quiz_id)
            rows = list(session.scalars(query)); result = []
            for row in rows:
                source_ids = list(session.scalars(select(QuestionSource.source_fragment_id).where(QuestionSource.question_id == row.id)))
                result.append(self._view(session, "quiz_question", row.id, self._question_snapshot(row, source_ids)))
            return result

    def update_question(self, question_id: UUID, changes: dict[str, Any], *, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        allowed = {"prompt", "question_type", "answer_payload", "source_fragment_ids"}
        if set(changes) - allowed: raise ApplicationError("practice_fields_invalid", "Question contains unsupported fields", 422)
        with self._session_factory() as session:
            row = session.get(QuizQuestion, question_id)
            if row is None: raise ApplicationError("question_not_found", "Quiz question was not found", 404)
            self._ensure_version(session, "quiz_question", question_id, expected_version)
            old_sources = list(session.scalars(select(QuestionSource.source_fragment_id).where(QuestionSource.question_id == question_id))); before = self._question_snapshot(row, old_sources)
            question_type = changes.get("question_type", row.question_type); answer_payload = changes.get("answer_payload", row.answer_payload); self._validate_answer(question_type, answer_payload)
            for field in ("prompt", "question_type", "answer_payload"):
                if field in changes: setattr(row, field, changes[field].strip() if isinstance(changes[field], str) else changes[field])
            source_ids = changes.get("source_fragment_ids", old_sources)
            if "source_fragment_ids" in changes:
                session.execute(delete(QuestionSource).where(QuestionSource.question_id == question_id))
                for source_id in source_ids:
                    if session.get(SourceFragment, source_id) is None: raise ApplicationError("fragment_not_found", "Source fragment was not found", 404)
                    session.add(QuestionSource(question_id=question_id, source_fragment_id=source_id))
            row.is_published = False; snapshot = self._question_snapshot(row, source_ids); version = self._revision(session, "quiz_question", row.id, snapshot, actor_id, "draft"); session.commit()
        result = {"id": question_id, **snapshot, "version": version, "status": "draft"}; self._record(actor_id, "quiz_question.updated", question_id, before, result, **context); return result

    def publish_question(self, question_id: UUID, *, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(QuizQuestion, question_id)
            if row is None: raise ApplicationError("question_not_found", "Quiz question was not found", 404)
            self._ensure_version(session, "quiz_question", question_id, expected_version)
            sources = list(session.scalars(select(SourceFragment).join(QuestionSource, QuestionSource.source_fragment_id == SourceFragment.id).where(QuestionSource.question_id == question_id)))
            if not sources or any(item.review_status != ReviewStatus.VERIFIED or not item.is_published or item.printed_page is None for item in sources): raise ApplicationError("grounding_required", "Verified published textbook sources with pages are required", 422)
            before = self._question_snapshot(row, [item.id for item in sources]); row.is_published = True; snapshot = self._question_snapshot(row, [item.id for item in sources]); version = self._revision(session, "quiz_question", row.id, snapshot, actor_id, "published"); session.commit()
        result = {"id": question_id, **snapshot, "version": version, "status": "published"}; self._record(actor_id, "quiz_question.published", question_id, before, result, **context); return result

    def archive_question(self, question_id: UUID, *, expected_version: int, actor_id: UUID, **context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(QuizQuestion, question_id)
            if row is None: raise ApplicationError("question_not_found", "Quiz question was not found", 404)
            self._ensure_version(session, "quiz_question", question_id, expected_version); source_ids = list(session.scalars(select(QuestionSource.source_fragment_id).where(QuestionSource.question_id == question_id))); before = self._question_snapshot(row, source_ids); row.is_published = False; snapshot = self._question_snapshot(row, source_ids); version = self._revision(session, "quiz_question", row.id, snapshot, actor_id, "archived"); session.commit()
        result = {"id": question_id, **snapshot, "version": version, "status": "archived"}; self._record(actor_id, "quiz_question.archived", question_id, before, result, **context); return result

    def delete_question(self, question_id: UUID, *, actor_id: UUID, **context: Any) -> None:
        with self._session_factory() as session:
            row = session.get(QuizQuestion, question_id)
            if row is None: raise ApplicationError("question_not_found", "Quiz question was not found", 404)
            if session.scalar(select(StudentAnswer.id).where(StudentAnswer.question_id == question_id).limit(1)) is not None: raise ApplicationError("practice_content_in_use", "Archive practice content that has learner data", 409)
            sources = list(session.scalars(select(QuestionSource.source_fragment_id).where(QuestionSource.question_id == question_id))); before = self._question_snapshot(row, sources); session.execute(delete(QuestionSource).where(QuestionSource.question_id == question_id)); session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "quiz_question", ContentRevision.entity_id == question_id)); session.delete(row); session.commit()
        self._record(actor_id, "quiz_question.deleted", question_id, before=before, **context)

    @staticmethod
    def _validate_answer(question_type: str, payload: dict[str, Any]) -> None:
        if question_type == "multiple_choice" and (not isinstance(payload.get("options"), list) or payload.get("correct_answer") not in payload.get("options", [])):
            raise ApplicationError("answer_payload_invalid", "Multiple choice requires options and a matching correct answer", 422)
        if question_type == "true_false" and not isinstance(payload.get("correct_answer"), bool):
            raise ApplicationError("answer_payload_invalid", "True/false requires a boolean correct answer", 422)

    def _pronounce(self, word: str) -> str | None:
        if self._pronunciation_provider is None: return None
        try: return self._pronunciation_provider.pronounce(word.strip())
        except AIProviderError: return None

    def _view(self, session: Session, entity_type: str, entity_id: UUID, snapshot: dict[str, Any]) -> dict[str, Any]:
        version = self._current_version(session, entity_type, entity_id)
        status = session.scalar(select(ContentRevision.status).where(ContentRevision.entity_type == entity_type, ContentRevision.entity_id == entity_id).order_by(ContentRevision.version.desc()).limit(1)) or "draft"
        return {"id": entity_id, **snapshot, "version": version, "status": status}

    def versions(self, entity_type: str, entity_id: UUID) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = list(session.scalars(select(ContentRevision).where(ContentRevision.entity_type == entity_type, ContentRevision.entity_id == entity_id).order_by(ContentRevision.version.desc())))
            return [{"version": row.version, "status": row.status, "snapshot": row.snapshot, "created_at": row.created_at} for row in rows]

    def preview(self, entity_type: str, entity_id: UUID) -> dict[str, Any]:
        with self._session_factory() as session:
            if entity_type == "quiz_blueprint": row, snapshotter = session.get(QuizBlueprint, entity_id), self._blueprint_snapshot
            elif entity_type == "flashcard_deck": row, snapshotter = session.get(FlashcardDeck, entity_id), self._deck_snapshot
            elif entity_type == "flashcard": row, snapshotter = session.get(Flashcard, entity_id), self._card_snapshot
            elif entity_type == "quiz_question":
                row = session.get(QuizQuestion, entity_id)
                if row is None: raise ApplicationError("practice_content_not_found", "Practice content was not found", 404)
                source_ids = list(session.scalars(select(QuestionSource.source_fragment_id).where(QuestionSource.question_id == entity_id)))
                return self._view(session, entity_type, entity_id, self._question_snapshot(row, source_ids))
            else: raise ApplicationError("practice_content_type_invalid", "Practice content type is invalid", 422)
            if row is None: raise ApplicationError("practice_content_not_found", "Practice content was not found", 404)
            return self._view(session, entity_type, entity_id, snapshotter(row))
