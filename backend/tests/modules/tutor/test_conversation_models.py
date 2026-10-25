from datetime import datetime, timedelta, timezone
from uuid import uuid4

from english7.db.models import TutorChat, TutorConversation


def test_tutor_exchange_belongs_to_ordered_conversation() -> None:
    owner_id = uuid4()
    conversation_id = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    conversation = TutorConversation(
        id=conversation_id,
        user_id=owner_id,
        title="Unit 1 grammar",
        language="en",
        addressing_preference=None,
        expires_at=expires_at,
    )
    exchange = TutorChat(
        user_id=owner_id,
        conversation_id=conversation_id,
        sequence_number=1,
        question="Why do we add -s?",
        answer="We add -s with he, she, and it.",
        language="en",
        citations=[],
    )

    assert conversation.id == conversation_id
    assert conversation.expires_at == expires_at
    assert exchange.conversation_id == conversation_id
    assert exchange.sequence_number == 1


def test_conversation_tables_define_limit_query_indexes() -> None:
    conversation_indexes = {
        index.name for index in TutorConversation.__table__.indexes
    }
    chat_indexes = {index.name for index in TutorChat.__table__.indexes}

    assert "ix_tutor_conversations_owner_updated" in conversation_indexes
    assert "ix_tutor_chats_conversation_sequence" in chat_indexes
