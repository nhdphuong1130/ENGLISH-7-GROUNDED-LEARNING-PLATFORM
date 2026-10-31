from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from english7.api.errors import ApplicationError
from english7.db.models import TutorChat, TutorConversation


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    id: UUID
    user_id: UUID
    title: str
    language: str
    addressing_preference: str | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ExchangeRecord:
    id: UUID
    conversation_id: UUID
    sequence_number: int
    question: str
    answer: str
    language: str
    upload_id: UUID | None
    citations: tuple[dict, ...]
    created_at: datetime


class ConversationRepository(Protocol):
    def cleanup_expired(self, owner_id: UUID, now: datetime) -> None: ...

    def create(
        self,
        *,
        owner_id: UUID,
        title: str,
        language: str,
        expires_at: datetime,
        now: datetime,
    ) -> ConversationRecord: ...

    def list_for_owner(self, owner_id: UUID) -> tuple[ConversationRecord, ...]: ...

    def get_for_owner(
        self, owner_id: UUID, conversation_id: UUID
    ) -> ConversationRecord | None: ...

    def delete_for_owner(self, owner_id: UUID, conversation_id: UUID) -> bool: ...

    def count_for_owner(self, owner_id: UUID) -> int: ...

    def delete_oldest_for_owner(self, owner_id: UUID) -> bool: ...

    def exchange_count(self, owner_id: UUID, conversation_id: UUID) -> int: ...

    def recent_exchanges(
        self, owner_id: UUID, conversation_id: UUID, limit: int
    ) -> tuple[ExchangeRecord, ...]: ...

    def append_exchange(
        self,
        *,
        owner_id: UUID,
        conversation_id: UUID,
        question: str,
        answer: str,
        language: str,
        upload_id: UUID | None,
        citations: list[dict],
        now: datetime,
        expires_at: datetime,
    ) -> ExchangeRecord | None: ...

    def set_addressing_preference(
        self,
        owner_id: UUID,
        conversation_id: UUID,
        preference: str | None,
        now: datetime,
        expires_at: datetime,
    ) -> ConversationRecord | None: ...


class SQLAlchemyConversationRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._sessions = session_factory

    @staticmethod
    def _conversation(row: TutorConversation) -> ConversationRecord:
        return ConversationRecord(
            id=row.id,
            user_id=row.user_id,
            title=row.title,
            language=row.language,
            addressing_preference=row.addressing_preference,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _exchange(row: TutorChat) -> ExchangeRecord:
        return ExchangeRecord(
            id=row.id,
            conversation_id=row.conversation_id,
            sequence_number=row.sequence_number,
            question=row.question,
            answer=row.answer,
            language=row.language,
            upload_id=row.upload_id,
            citations=tuple(row.citations or ()),
            created_at=row.created_at,
        )

    def cleanup_expired(self, owner_id: UUID, now: datetime) -> None:
        with self._sessions() as session:
            session.execute(
                delete(TutorConversation).where(
                    TutorConversation.user_id == owner_id,
                    TutorConversation.expires_at <= now,
                )
            )
            session.commit()

    def create(
        self,
        *,
        owner_id: UUID,
        title: str,
        language: str,
        expires_at: datetime,
        now: datetime,
    ) -> ConversationRecord:
        row = TutorConversation(
            id=uuid4(),
            user_id=owner_id,
            title=title,
            language=language,
            addressing_preference=None,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        with self._sessions() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._conversation(row)

    def list_for_owner(self, owner_id: UUID) -> tuple[ConversationRecord, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(TutorConversation)
                .where(TutorConversation.user_id == owner_id)
                .order_by(
                    TutorConversation.updated_at.desc(),
                    TutorConversation.id.desc(),
                )
            ).all()
            return tuple(self._conversation(row) for row in rows)

    def get_for_owner(
        self, owner_id: UUID, conversation_id: UUID
    ) -> ConversationRecord | None:
        with self._sessions() as session:
            row = session.scalar(
                select(TutorConversation).where(
                    TutorConversation.id == conversation_id,
                    TutorConversation.user_id == owner_id,
                )
            )
            return self._conversation(row) if row else None

    def delete_for_owner(self, owner_id: UUID, conversation_id: UUID) -> bool:
        with self._sessions() as session:
            result = session.execute(
                delete(TutorConversation).where(
                    TutorConversation.id == conversation_id,
                    TutorConversation.user_id == owner_id,
                )
            )
            session.commit()
            return bool(result.rowcount)

    def count_for_owner(self, owner_id: UUID) -> int:
        with self._sessions() as session:
            return int(
                session.scalar(
                    select(func.count(TutorConversation.id)).where(
                        TutorConversation.user_id == owner_id
                    )
                )
                or 0
            )

    def delete_oldest_for_owner(self, owner_id: UUID) -> bool:
        with self._sessions() as session:
            conversation_id = session.scalar(
                select(TutorConversation.id)
                .where(TutorConversation.user_id == owner_id)
                .order_by(
                    TutorConversation.updated_at.asc(),
                    TutorConversation.id.asc(),
                )
                .limit(1)
            )
            if conversation_id is None:
                return False
            session.execute(
                delete(TutorConversation).where(
                    TutorConversation.id == conversation_id
                )
            )
            session.commit()
            return True

    def exchange_count(self, owner_id: UUID, conversation_id: UUID) -> int:
        with self._sessions() as session:
            return int(
                session.scalar(
                    select(func.count(TutorChat.id))
                    .join(
                        TutorConversation,
                        TutorChat.conversation_id == TutorConversation.id,
                    )
                    .where(
                        TutorConversation.user_id == owner_id,
                        TutorChat.conversation_id == conversation_id,
                    )
                )
                or 0
            )

    def recent_exchanges(
        self, owner_id: UUID, conversation_id: UUID, limit: int
    ) -> tuple[ExchangeRecord, ...]:
        with self._sessions() as session:
            rows = session.scalars(
                select(TutorChat)
                .join(
                    TutorConversation,
                    TutorChat.conversation_id == TutorConversation.id,
                )
                .where(
                    TutorConversation.user_id == owner_id,
                    TutorChat.conversation_id == conversation_id,
                )
                .order_by(TutorChat.sequence_number.desc())
                .limit(limit)
            ).all()
            return tuple(self._exchange(row) for row in reversed(rows))

    def append_exchange(
        self,
        *,
        owner_id: UUID,
        conversation_id: UUID,
        question: str,
        answer: str,
        language: str,
        upload_id: UUID | None,
        citations: list[dict],
        now: datetime,
        expires_at: datetime,
    ) -> ExchangeRecord | None:
        with self._sessions() as session:
            conversation = session.scalar(
                select(TutorConversation).where(
                    TutorConversation.id == conversation_id,
                    TutorConversation.user_id == owner_id,
                )
            )
            if conversation is None:
                return None
            sequence_number = int(
                session.scalar(
                    select(func.max(TutorChat.sequence_number)).where(
                        TutorChat.conversation_id == conversation_id
                    )
                )
                or 0
            ) + 1
            row = TutorChat(
                id=uuid4(),
                user_id=owner_id,
                conversation_id=conversation_id,
                sequence_number=sequence_number,
                question=question,
                answer=answer,
                language=language,
                upload_id=upload_id,
                citations=citations,
                created_at=now,
                updated_at=now,
            )
            conversation.updated_at = now
            conversation.expires_at = expires_at
            if sequence_number == 1 and conversation.title in ("Đoạn chat mới", "Tutor conversation", "New chat"):
                conversation.title = " ".join(question.split())[:160] or conversation.title
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._exchange(row)

    def set_addressing_preference(
        self,
        owner_id: UUID,
        conversation_id: UUID,
        preference: str | None,
        now: datetime,
        expires_at: datetime,
    ) -> ConversationRecord | None:
        with self._sessions() as session:
            row = session.scalar(
                select(TutorConversation).where(
                    TutorConversation.id == conversation_id,
                    TutorConversation.user_id == owner_id,
                )
            )
            if row is None:
                return None
            row.addressing_preference = preference
            row.updated_at = now
            row.expires_at = expires_at
            session.commit()
            session.refresh(row)
            return self._conversation(row)


class ConversationHistoryService:
    def __init__(
        self,
        repository: ConversationRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
        maximum_conversations: int = 20,
        maximum_exchanges: int = 50,
        context_exchanges: int = 6,
        retention: timedelta = timedelta(days=90),
    ) -> None:
        if min(maximum_conversations, maximum_exchanges, context_exchanges) <= 0:
            raise ValueError("Conversation limits must be positive")
        if retention <= timedelta(0):
            raise ValueError("Conversation retention must be positive")
        self._repository = repository
        self._clock = clock
        self._maximum_conversations = maximum_conversations
        self._maximum_exchanges = maximum_exchanges
        self._context_exchanges = context_exchanges
        self._retention = retention

    def _cleanup(self, owner_id: UUID) -> datetime:
        now = self._clock()
        self._repository.cleanup_expired(owner_id, now)
        return now

    def create(
        self, owner_id: UUID, language: str, title: str
    ) -> ConversationRecord:
        now = self._cleanup(owner_id)
        while self._repository.count_for_owner(owner_id) >= self._maximum_conversations:
            if not self._repository.delete_oldest_for_owner(owner_id):
                break
        normalized_title = " ".join(title.split())[:160] or "Tutor conversation"
        return self._repository.create(
            owner_id=owner_id,
            title=normalized_title,
            language=language,
            expires_at=now + self._retention,
            now=now,
        )

    def list(self, owner_id: UUID) -> tuple[ConversationRecord, ...]:
        self._cleanup(owner_id)
        return self._repository.list_for_owner(owner_id)

    def get(
        self, owner_id: UUID, conversation_id: UUID
    ) -> ConversationRecord | None:
        self._cleanup(owner_id)
        return self._repository.get_for_owner(owner_id, conversation_id)

    def delete(self, owner_id: UUID, conversation_id: UUID) -> bool:
        return self._repository.delete_for_owner(owner_id, conversation_id)

    def ensure_can_ask(
        self, owner_id: UUID, conversation_id: UUID
    ) -> ConversationRecord:
        conversation = self.get(owner_id, conversation_id)
        if conversation is None:
            raise ApplicationError(
                "conversation_not_found", "Conversation was not found", 404
            )
        if (
            self._repository.exchange_count(owner_id, conversation_id)
            >= self._maximum_exchanges
        ):
            raise ApplicationError(
                "conversation_full",
                "This conversation has reached its exchange limit",
                409,
            )
        return conversation

    def context_for_ask(
        self, owner_id: UUID, conversation_id: UUID
    ) -> tuple[ExchangeRecord, ...]:
        if self.get(owner_id, conversation_id) is None:
            raise ApplicationError(
                "conversation_not_found", "Conversation was not found", 404
            )
        return self._repository.recent_exchanges(
            owner_id, conversation_id, self._context_exchanges
        )

    def exchanges(
        self, owner_id: UUID, conversation_id: UUID
    ) -> tuple[ExchangeRecord, ...]:
        if self.get(owner_id, conversation_id) is None:
            raise ApplicationError(
                "conversation_not_found", "Conversation was not found", 404
            )
        return self._repository.recent_exchanges(
            owner_id, conversation_id, self._maximum_exchanges
        )

    def append_exchange(
        self,
        *,
        owner_id: UUID,
        conversation_id: UUID,
        question: str,
        answer: str,
        language: str,
        citations: list[dict],
        upload_id: UUID | None = None,
    ) -> ExchangeRecord:
        self.ensure_can_ask(owner_id, conversation_id)
        now = self._clock()
        row = self._repository.append_exchange(
            owner_id=owner_id,
            conversation_id=conversation_id,
            question=question,
            answer=answer,
            language=language,
            upload_id=upload_id,
            citations=citations,
            now=now,
            expires_at=now + self._retention,
        )
        if row is None:
            raise ApplicationError(
                "conversation_not_found", "Conversation was not found", 404
            )
        return row

    def set_addressing_preference(
        self,
        owner_id: UUID,
        conversation_id: UUID,
        preference: str | None,
    ) -> ConversationRecord | None:
        normalized = " ".join((preference or "").split())[:120] or None
        now = self._clock()
        return self._repository.set_addressing_preference(
            owner_id,
            conversation_id,
            normalized,
            now,
            now + self._retention,
        )
