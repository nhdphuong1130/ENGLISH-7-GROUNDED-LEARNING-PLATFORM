from collections.abc import Callable
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import delete, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from english7.api.errors import ApplicationError
from english7.modules.flashcards.models import Flashcard, FlashcardDeck, FlashcardReview, FlashcardState


class SQLAlchemyFlashcardRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    @contextmanager
    def transaction(self):
        try:
            with self.session_factory() as session, session.begin():
                yield FlashcardTransaction(session)
        except IntegrityError as error:
            raise ApplicationError('flashcard_conflict', 'A conflicting change was saved; reload and retry', 409) from error


class FlashcardTransaction:
    def __init__(self, session: Session):
        self.session = session

    def decks(self, user_id: UUID):
        return list(self.session.scalars(select(FlashcardDeck).where(or_(FlashcardDeck.owner_id == user_id, (FlashcardDeck.kind == 'textbook') & FlashcardDeck.is_active.is_(True))).order_by(FlashcardDeck.unit_number, FlashcardDeck.name)))

    def deck(self, deck_id):
        return self.session.get(FlashcardDeck, deck_id)

    def card(self, card_id):
        return self.session.get(Flashcard, card_id)

    def cards(self, deck_id):
        deck = self.deck(deck_id)
        query = select(Flashcard).where(Flashcard.deck_id == deck_id)
        if deck is not None and deck.kind == 'textbook':
            query = query.where(Flashcard.is_published.is_(True))
        return list(self.session.scalars(query.order_by(Flashcard.word)))

    def state(self, user_id, card_id, create=False):
        state = self.session.scalar(select(FlashcardState).where(FlashcardState.user_id == user_id, FlashcardState.card_id == card_id).with_for_update().with_hint(FlashcardState, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql'))
        if state is None and create:
            state = FlashcardState(user_id=user_id, card_id=card_id, review_count=0, successful_reviews=0, difficult=False)
            self.session.add(state)
        return state

    def review(self, user_id, request_id):
        return self.session.scalar(select(FlashcardReview).where(FlashcardReview.user_id == user_id, FlashcardReview.request_id == request_id))

    def create_deck(self, **values):
        row = FlashcardDeck(**values)
        self.session.add(row)
        self.session.flush()
        return row

    def create_card(self, **values):
        row = Flashcard(**values)
        self.session.add(row)
        self.session.flush()
        return row

    def create_review(self, **values):
        self.session.add(FlashcardReview(**values))

    def delete_card(self, card):
        self.session.execute(delete(FlashcardReview).where(FlashcardReview.card_id == card.id))
        self.session.execute(delete(FlashcardState).where(FlashcardState.card_id == card.id))
        self.session.delete(card)

    def delete_deck(self, deck):
        for card in self.cards(deck.id):
            self.delete_card(card)
        self.session.flush()
        self.session.delete(deck)

    def textbook_deck(self, unit_id):
        return self.session.scalar(select(FlashcardDeck).where(FlashcardDeck.kind == 'textbook', FlashcardDeck.unit_id == unit_id))

    def verified_sources(self):
        from english7.db.models import Activity, Section, SourceDocument, SourceFragment, Unit
        statement = (
            select(Unit, SourceFragment)
            .join(Section, Section.unit_id == Unit.id)
            .join(Activity, Activity.section_id == Section.id)
            .join(SourceFragment, SourceFragment.activity_id == Activity.id)
            .join(SourceDocument, SourceDocument.id == SourceFragment.source_document_id)
            .where(
                Unit.is_published == true(),
                SourceDocument.textbook_id == Unit.textbook_id,
                SourceFragment.review_status == 'verified',
                SourceFragment.is_published == true(),
                SourceFragment.printed_page.is_not(None),
                SourceFragment.printed_page > 0,
            )
            .order_by(Unit.number, SourceFragment.printed_page)
        )
        return list(self.session.execute(statement))
