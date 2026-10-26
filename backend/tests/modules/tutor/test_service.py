from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from english7.api.errors import ApplicationError
from english7.modules.ai.contracts import (
    AIProviderError,
    AIResponse,
    Language,
    ScopeStatus,
)
from english7.modules.retrieval.service import (
    Citation,
    GroundedContext,
    RetrievalCandidate,
)
from english7.modules.tutor.service import TutorService
from english7.modules.tutor.conversations import ConversationRecord, ExchangeRecord


def grounded_context() -> GroundedContext:
    fragment = RetrievalCandidate(
        fragment_id=uuid4(),
        unit_number=2,
        text="Exercise every day to stay healthy.",
        pdf_page=22,
        printed_page=20,
        vector_score=0.94,
        has_verified_source=True,
        hierarchy=("English 7", "Unit 2", "A Closer Look", "Activity 2"),
    )
    return GroundedContext(
        (fragment,),
        (Citation(fragment.fragment_id, fragment.pdf_page, fragment.printed_page),),
    )


class FakeRetrieval:
    def __init__(self, context: GroundedContext) -> None:
        self.context = context
        self.queries = []

    def retrieve(self, query: str) -> GroundedContext:
        self.queries.append(query)
        return self.context


class FakeProvider:
    def __init__(self, responder) -> None:
        self.responder = responder
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.responder(request)


class FakeConversations:
    def __init__(self, owner_id, exchanges=()) -> None:
        now = datetime.now(timezone.utc)
        self.record = ConversationRecord(
            id=uuid4(),
            user_id=owner_id,
            title="Unit 2 health",
            language="en",
            addressing_preference="cô-em",
            expires_at=now + timedelta(days=90),
            created_at=now,
            updated_at=now,
        )
        self.exchanges = tuple(exchanges)
        self.appended = []

    def ensure_can_ask(self, owner_id, conversation_id):
        assert owner_id == self.record.user_id
        assert conversation_id == self.record.id
        return self.record

    def context_for_ask(self, owner_id, conversation_id):
        return self.exchanges[-6:]

    def append_exchange(self, **values):
        self.appended.append(values)

    def set_addressing_preference(self, owner_id, conversation_id, preference):
        self.record = ConversationRecord(
            id=self.record.id,
            user_id=self.record.user_id,
            title=self.record.title,
            language=self.record.language,
            addressing_preference=preference,
            expires_at=self.record.expires_at,
            created_at=self.record.created_at,
            updated_at=self.record.updated_at,
        )
        return self.record


def test_tutor_does_not_call_llm_without_grounded_context() -> None:
    provider = FakeProvider(lambda _: pytest.fail("provider must not be called"))
    service = TutorService(FakeRetrieval(GroundedContext((), ())), provider)

    answer = service.ask("Tell me about algebra", Language.ENGLISH)

    assert answer.scope_status is ScopeStatus.OUT_OF_SCOPE
    assert answer.citations == ()
    assert "English 7" in answer.answer
    assert provider.requests == []


def test_greeting_without_textbook_context_uses_ai_as_a_social_turn() -> None:
    provider = FakeProvider(
        lambda request: AIResponse(
            "Chào bạn! Hôm nay bạn muốn cùng mình học phần nào?",
            request.language,
            (),
            ScopeStatus.SOCIAL,
        )
    )
    retrieval = FakeRetrieval(GroundedContext((), ()))
    service = TutorService(retrieval, provider)

    answer = service.ask("xin chào", Language.VIETNAMESE)

    assert answer.scope_status is ScopeStatus.SOCIAL
    assert answer.citations == ()
    assert "học phần nào" in answer.answer
    assert provider.requests[0].social_turn is True
    assert provider.requests[0].evidence == ()


def test_unrelated_question_without_context_remains_out_of_scope() -> None:
    provider = FakeProvider(lambda _: pytest.fail("provider must not be called"))
    service = TutorService(FakeRetrieval(GroundedContext((), ())), provider)

    answer = service.ask("Tell me about algebra", Language.ENGLISH)

    assert answer.scope_status is ScopeStatus.OUT_OF_SCOPE


def test_conversation_history_is_bounded_context_and_never_evidence() -> None:
    owner_id = uuid4()
    exchanges = tuple(
        ExchangeRecord(
            id=uuid4(),
            conversation_id=uuid4(),
            sequence_number=number,
            question=f"q{number}",
            answer=f"a{number}",
            language="en",
            upload_id=None,
            citations=(),
            created_at=datetime.now(timezone.utc),
        )
        for number in range(1, 9)
    )
    conversations = FakeConversations(owner_id, exchanges)
    context = grounded_context()
    provider = FakeProvider(
        lambda request: AIResponse(
            "Grounded answer",
            request.language,
            (request.evidence[0].fragment_id,),
        )
    )
    retrieval = FakeRetrieval(context)
    service = TutorService(retrieval, provider, conversations=conversations)

    service.ask(
        "Why is exercise useful?",
        Language.ENGLISH,
        user_id=owner_id,
        conversation_id=conversations.record.id,
    )

    request = provider.requests[0]
    assert [turn.learner for turn in request.history] == [
        "q3", "q4", "q5", "q6", "q7", "q8"
    ]
    assert tuple(item.text for item in request.evidence) == (
        "Exercise every day to stay healthy.",
    )
    assert request.addressing_preference == "cô-em"
    assert retrieval.queries == ["Why is exercise useful?"]
    assert len(conversations.appended) == 1


def test_tutor_rejects_citation_not_present_in_context() -> None:
    context = grounded_context()
    provider = FakeProvider(
        lambda request: AIResponse(
            "Unsupported", request.language, (uuid4(),)
        )
    )
    service = TutorService(FakeRetrieval(context), provider)

    with pytest.raises(ApplicationError) as captured:
        service.ask("How can I stay healthy?", Language.ENGLISH)

    assert captured.value.code == "invalid_ai_citations"


def test_language_mode_changes_presentation_but_not_evidence() -> None:
    context = grounded_context()

    def respond(request):
        answer = "Tập thể dục mỗi ngày." if request.language == "vi" else "Exercise daily."
        return AIResponse(answer, request.language, (request.evidence[0].fragment_id,))

    provider = FakeProvider(respond)
    service = TutorService(FakeRetrieval(context), provider)

    vietnamese = service.ask("How can I stay healthy?", Language.VIETNAMESE)
    english = service.ask("How can I stay healthy?", Language.ENGLISH)

    assert vietnamese.answer != english.answer
    assert provider.requests[0].evidence == provider.requests[1].evidence
    assert vietnamese.citations == english.citations


def test_tutor_rejects_language_mismatch() -> None:
    context = grounded_context()
    provider = FakeProvider(
        lambda request: AIResponse(
            "Wrong language", Language.ENGLISH, (request.evidence[0].fragment_id,)
        )
    )
    service = TutorService(FakeRetrieval(context), provider)

    with pytest.raises(ApplicationError) as captured:
        service.ask("Giữ sức khỏe thế nào?", Language.VIETNAMESE)

    assert captured.value.code == "invalid_ai_response"


def test_provider_failure_is_safe_and_does_not_append_exchange() -> None:
    owner_id = uuid4()
    conversations = FakeConversations(owner_id)
    provider = FakeProvider(
        lambda _: (_ for _ in ()).throw(AIProviderError("ai_provider_failed"))
    )
    service = TutorService(
        FakeRetrieval(grounded_context()),
        provider,
        conversations=conversations,
    )

    with pytest.raises(ApplicationError) as captured:
        service.ask(
            "How can I stay healthy?",
            Language.ENGLISH,
            user_id=owner_id,
            conversation_id=conversations.record.id,
        )

    assert captured.value.code == "ai_provider_unavailable"
    assert captured.value.status_code == 503
    assert conversations.appended == []
