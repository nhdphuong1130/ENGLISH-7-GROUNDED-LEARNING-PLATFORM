from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Unicode, UnicodeText, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from english7.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FlashcardDeck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = 'flashcard_decks'
    __table_args__ = (CheckConstraint("(kind = 'textbook' AND owner_id IS NULL) OR (kind = 'personal' AND owner_id IS NOT NULL)", name='ck_flashcard_deck_owner'),)

    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    kind: Mapped[str] = mapped_column(String(20), default='personal')
    unit_number: Mapped[int | None] = mapped_column(Integer)
    unit_id: Mapped[UUID | None] = mapped_column(ForeignKey('units.id'))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Flashcard(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = 'flashcards'
    __table_args__ = (UniqueConstraint('deck_id', 'normalized_word', name='uq_flashcard_word'),)

    deck_id: Mapped[UUID] = mapped_column(ForeignKey('flashcard_decks.id'), index=True)
    word: Mapped[str] = mapped_column(Unicode(200))
    normalized_word: Mapped[str] = mapped_column(Unicode(200))
    meaning: Mapped[str] = mapped_column(Unicode(1000))
    example: Mapped[str] = mapped_column(UnicodeText, default='')
    notes: Mapped[str] = mapped_column(UnicodeText, default='')
    image_url: Mapped[str | None] = mapped_column(Unicode(2048))
    ipa: Mapped[str | None] = mapped_column(Unicode(200))
    pos: Mapped[str | None] = mapped_column(Unicode(100))
    source_fragment_id: Mapped[UUID | None] = mapped_column(ForeignKey('source_fragments.id'))
    unit_number: Mapped[int | None] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    audio_url: Mapped[str | None] = mapped_column(Unicode(2048))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FlashcardState(Base, UUIDPrimaryKeyMixin):
    __tablename__ = 'flashcard_states'
    __table_args__ = (UniqueConstraint('user_id', 'card_id', name='uq_flashcard_state'),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    card_id: Mapped[UUID] = mapped_column(ForeignKey('flashcards.id'), index=True)
    difficult: Mapped[bool] = mapped_column(Boolean, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    successful_reviews: Mapped[int] = mapped_column(Integer, default=0)


class FlashcardReview(Base, UUIDPrimaryKeyMixin):
    __tablename__ = 'flashcard_reviews'
    __table_args__ = (UniqueConstraint('user_id', 'request_id', name='uq_flashcard_review_request'),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    card_id: Mapped[UUID] = mapped_column(ForeignKey('flashcards.id'), index=True)
    request_id: Mapped[UUID] = mapped_column()
    payload_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
