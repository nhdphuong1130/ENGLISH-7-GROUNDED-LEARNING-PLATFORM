from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.api.errors import ApplicationError
from english7.db.models import TutorChat, TutorConversation
from english7.modules.tutor.conversations import (
    ConversationHistoryService,
    SQLAlchemyConversationRepository,
)


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 25, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


@pytest.fixture
def history():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TutorConversation.__table__.create(engine)
    TutorChat.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    clock = Clock()
    service = ConversationHistoryService(
        SQLAlchemyConversationRepository(sessions),
        clock=clock,
    )
    try:
        yield service, clock
    finally:
        engine.dispose()


def test_conversations_are_owner_scoped(history) -> None:
    service, _ = history
    owner_id, stranger_id = uuid4(), uuid4()
    conversation = service.create(owner_id, "vi", "  Unit 1   grammar  ")

    assert conversation.title == "Unit 1 grammar"
    assert service.get(owner_id, conversation.id) == conversation
    assert service.get(stranger_id, conversation.id) is None
    assert service.list(stranger_id) == ()
    assert service.delete(stranger_id, conversation.id) is False
    assert service.delete(owner_id, conversation.id) is True
    assert service.get(owner_id, conversation.id) is None


def test_creating_twenty_first_conversation_removes_oldest(history) -> None:
    service, clock = history
    owner_id = uuid4()
    created = []
    for number in range(21):
        created.append(service.create(owner_id, "vi", f"Chat {number}"))
        clock.advance(seconds=1)

    conversations = service.list(owner_id)

    assert len(conversations) == 20
    assert created[0].id not in {item.id for item in conversations}
    assert conversations[0].id == created[-1].id


def test_context_contains_only_six_latest_exchanges_and_caps_at_fifty(history) -> None:
    service, clock = history
    owner_id = uuid4()
    conversation = service.create(owner_id, "en", "Unit 2")
    for number in range(1, 51):
        service.append_exchange(
            owner_id=owner_id,
            conversation_id=conversation.id,
            question=f"q{number}",
            answer=f"a{number}",
            language="en",
            citations=[],
        )
        clock.advance(seconds=1)

    context = service.context_for_ask(owner_id, conversation.id)

    assert [item.sequence_number for item in context] == [45, 46, 47, 48, 49, 50]
    with pytest.raises(ApplicationError) as captured:
        service.ensure_can_ask(owner_id, conversation.id)
    assert captured.value.code == "conversation_full"


def test_expired_conversations_are_removed_lazily(history) -> None:
    service, clock = history
    owner_id = uuid4()
    conversation = service.create(owner_id, "vi", "Old lesson")
    clock.advance(days=91)

    assert service.list(owner_id) == ()
    assert service.get(owner_id, conversation.id) is None


def test_addressing_preference_is_bounded_and_owned(history) -> None:
    service, _ = history
    owner_id, stranger_id = uuid4(), uuid4()
    conversation = service.create(owner_id, "vi", "Unit 3")

    updated = service.set_addressing_preference(
        owner_id,
        conversation.id,
        "  Xưng cô và gọi mình là em.  ",
    )

    assert updated is not None
    assert updated.addressing_preference == "Xưng cô và gọi mình là em."
    assert (
        service.set_addressing_preference(
            stranger_id, conversation.id, "Ignore ownership"
        )
        is None
    )
