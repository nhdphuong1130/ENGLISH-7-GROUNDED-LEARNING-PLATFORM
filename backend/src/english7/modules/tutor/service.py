from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from english7.api.errors import ApplicationError
from english7.modules.ai.contracts import (
    AIProvider,
    AIRequest,
    ConversationTurn,
    Evidence,
    Language,
    ScopeStatus,
)
from english7.modules.image_uploads.domain import ImageUploadRecord, ImageUploadStatus
from english7.modules.retrieval.service import Citation, RetrievalRepository
from english7.modules.tutor.conversations import (
    ConversationHistoryService,
    ConversationRecord,
    ExchangeRecord,
)


@dataclass(frozen=True, slots=True)
class TutorCitation:
    fragment_id: UUID
    unit_number: int
    pdf_page: int
    printed_page: int | None
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class TutorAnswer:
    answer: str
    language: Language
    citations: tuple[TutorCitation | Citation, ...]
    scope_status: ScopeStatus = ScopeStatus.GROUNDED
    conversation_id: UUID | None = None


class ContextRetriever(RetrievalRepository):
    def retrieve(self, query: str): ...


class TutorUploadRepository(Protocol):
    def get_for_owner(
        self, upload_id: UUID, owner_id: UUID
    ) -> ImageUploadRecord | None: ...


class TutorService:
    def __init__(
        self,
        retrieval,
        provider: AIProvider,
        *,
        uploads: TutorUploadRepository | None = None,
        conversations: ConversationHistoryService | None = None,
        maximum_query_characters: int = 4000,
    ) -> None:
        if maximum_query_characters <= 0:
            raise ValueError("Maximum query characters must be positive")
        self._retrieval = retrieval
        self._provider = provider
        self._uploads = uploads
        self._conversations = conversations
        self._maximum_query_characters = maximum_query_characters

    def create_conversation(
        self,
        user_id: UUID,
        language: Language,
        title: str,
        addressing_preference: str | None = None,
    ) -> ConversationRecord:
        conversations = self._require_conversations()
        record = conversations.create(user_id, language.value, title)
        if addressing_preference:
            updated = conversations.set_addressing_preference(
                user_id, record.id, addressing_preference
            )
            if updated is not None:
                record = updated
        return record

    def list_conversations(
        self, user_id: UUID
    ) -> tuple[ConversationRecord, ...]:
        return self._require_conversations().list(user_id)

    def get_conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> tuple[ConversationRecord, tuple[ExchangeRecord, ...]]:
        conversations = self._require_conversations()
        record = conversations.get(user_id, conversation_id)
        if record is None:
            raise ApplicationError(
                "conversation_not_found", "Conversation was not found", 404
            )
        return record, conversations.exchanges(user_id, conversation_id)

    def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> bool:
        return self._require_conversations().delete(user_id, conversation_id)

    def _require_conversations(self) -> ConversationHistoryService:
        if self._conversations is None:
            raise ApplicationError(
                "conversation_unavailable",
                "Tutor conversation history is not configured",
                503,
            )
        return self._conversations

    @staticmethod
    def _out_of_scope(language: Language) -> str:
        if language is Language.VIETNAMESE:
            return (
                "Mình chỉ có thể hỗ trợ nội dung trong sách Tiếng Anh 7 "
                "Global Success. Bạn hãy hỏi về bài học, từ vựng, ngữ pháp "
                "hoặc bài tập trong sách nhé."
            )
        return (
            "I can only help with content from the English 7 Global Success "
            "textbook. Please ask about its lessons, vocabulary, grammar, or "
            "exercises."
        )

    def ask(
        self,
        question: str,
        language: Language,
        *,
        user_id: UUID | None = None,
        upload_id: UUID | None = None,
        conversation_id: UUID | None = None,
        addressing_preference: str | None = None,
    ) -> TutorAnswer:
        parts = [" ".join(question.split())] if question.strip() else []
        if upload_id is not None:
            if self._uploads is None or user_id is None:
                raise ApplicationError(
                    "image_upload_unavailable",
                    "Image upload support is not configured",
                    503,
                )
            upload = self._uploads.get_for_owner(upload_id, user_id)
            if upload is None:
                raise ApplicationError(
                    "image_upload_not_found", "Image upload was not found", 404
                )
            expires_at = upload.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise ApplicationError(
                    "image_upload_expired", "Image upload has expired", 410
                )
            if upload.status in {
                ImageUploadStatus.QUEUED,
                ImageUploadStatus.PROCESSING,
            }:
                raise ApplicationError(
                    "image_upload_not_ready", "Image is still being processed", 409
                )
            if upload.status is ImageUploadStatus.FAILED:
                code = upload.failure_code or "image_processing_failed"
                raise ApplicationError(code, "Image processing failed", 422)
            if not upload.ocr_text or not upload.ocr_text.strip():
                raise ApplicationError(
                    "image_text_not_found", "No usable text was found in the image", 422
                )
            parts.append(" ".join(upload.ocr_text.split()))
        query = "\n".join(parts)[: self._maximum_query_characters]
        if not query:
            raise ApplicationError("question_required", "A question is required", 422)

        conversation = None
        history: tuple[ExchangeRecord, ...] = ()
        if self._conversations is not None:
            if user_id is None:
                raise ApplicationError(
                    "authentication_required", "Authentication is required", 401
                )
            if conversation_id is None:
                conversation = self.create_conversation(
                    user_id,
                    language,
                    question or "Image question",
                    addressing_preference,
                )
                conversation_id = conversation.id
            else:
                conversation = self._conversations.ensure_can_ask(
                    user_id, conversation_id
                )
                if addressing_preference is not None:
                    updated = self._conversations.set_addressing_preference(
                        user_id, conversation_id, addressing_preference
                    )
                    if updated is not None:
                        conversation = updated
            history = self._conversations.context_for_ask(user_id, conversation_id)

        context = self._retrieval.retrieve(query)
        if not context.fragments:
            result = TutorAnswer(
                self._out_of_scope(language),
                language,
                (),
                ScopeStatus.OUT_OF_SCOPE,
                conversation_id,
            )
            self._persist_answer(
                result,
                user_id=user_id,
                question=question,
                upload_id=upload_id,
            )
            return result
        evidence = tuple(
            Evidence(
                item.fragment_id,
                item.text,
                item.pdf_page,
                item.printed_page,
            )
            for item in context.fragments
        )
        generated = self._provider.generate(
            AIRequest(
                query,
                language,
                evidence,
                history=tuple(
                    ConversationTurn(item.question, item.answer) for item in history
                ),
                addressing_preference=(
                    conversation.addressing_preference if conversation else None
                ),
            )
        )
        if generated.scope_status is ScopeStatus.OUT_OF_SCOPE:
            result = TutorAnswer(
                self._out_of_scope(language),
                language,
                (),
                ScopeStatus.OUT_OF_SCOPE,
                conversation_id,
            )
            self._persist_answer(
                result,
                user_id=user_id,
                question=question,
                upload_id=upload_id,
            )
            return result
        if generated.language != language or not generated.answer:
            raise ApplicationError(
                "invalid_ai_response", "AI response validation failed", 502
            )
        allowed = {item.fragment_id for item in evidence}
        if not generated.citations or not set(generated.citations).issubset(allowed):
            raise ApplicationError(
                "invalid_ai_citations", "AI citations failed source validation", 502
            )
        citations_by_id = {
            citation.fragment_id: citation for citation in context.citations
        }
        fragments_by_id = {
            fragment.fragment_id: fragment for fragment in context.fragments
        }
        try:
            citations = tuple(
                TutorCitation(
                    fragment_id=fragment_id,
                    unit_number=fragments_by_id[fragment_id].unit_number,
                    pdf_page=citations_by_id[fragment_id].pdf_page,
                    printed_page=citations_by_id[fragment_id].printed_page,
                    image_url=getattr(citations_by_id[fragment_id], "image_url", None),
                )
                for fragment_id in generated.citations
            )
        except KeyError:
            raise ApplicationError(
                "invalid_ai_citations", "AI citations failed source validation", 502
            ) from None
        result = TutorAnswer(
            generated.answer,
            generated.language,
            citations,
            ScopeStatus.GROUNDED,
            conversation_id,
        )
        self._persist_answer(
            result,
            user_id=user_id,
            question=question,
            upload_id=upload_id,
        )
        return result

    def _persist_answer(
        self,
        answer: TutorAnswer,
        *,
        user_id: UUID | None,
        question: str,
        upload_id: UUID | None,
    ) -> None:
        if (
            self._conversations is None
            or user_id is None
            or answer.conversation_id is None
        ):
            return
        self._conversations.append_exchange(
            owner_id=user_id,
            conversation_id=answer.conversation_id,
            question=question,
            answer=answer.answer,
            language=answer.language.value,
            upload_id=upload_id,
            citations=[
                {
                    "fragment_id": str(item.fragment_id),
                    "unit_number": getattr(item, "unit_number", None),
                    "pdf_page": item.pdf_page,
                    "printed_page": item.printed_page,
                    "image_url": getattr(item, "image_url", None),
                }
                for item in answer.citations
            ],
        )
