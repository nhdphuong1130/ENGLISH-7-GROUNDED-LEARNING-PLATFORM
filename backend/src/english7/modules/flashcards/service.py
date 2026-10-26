from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from uuid import UUID
from typing import Protocol

from english7.api.errors import ApplicationError
from english7.modules.ai.contracts import AIProviderError
from english7.modules.flashcards.domain import Card, Deck, ReviewResult, normalize_word


logger = logging.getLogger(__name__)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class PronunciationProvider(Protocol):
    def pronounce(self, text: str) -> str: ...


class FlashcardService:
    def __init__(
        self,
        repository,
        clock: Callable[[], datetime] | None = None,
        audio_cache=None,
        pronunciation_provider: PronunciationProvider | None = None,
    ):
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.audio_cache = audio_cache
        self.pronunciation_provider = pronunciation_provider

    def _pronunciation(self, word: str) -> str | None:
        if self.pronunciation_provider is None:
            return None
        try:
            return self.pronunciation_provider.pronounce(word)
        except AIProviderError:
            logger.warning("AI pronunciation is temporarily unavailable")
            return None

    def card_audio(self, user_id: UUID, card_id: UUID) -> bytes:
        card = self.get_card(user_id, card_id)
        if self.audio_cache is None:
            raise ApplicationError('speech_unavailable', 'Audio service is not configured', 503)
        return self.audio_cache.get_or_synthesize(card.word)

    @staticmethod
    def _deck(tx, user_id, deck_id, write=False):
        deck = tx.deck(deck_id)
        if deck is None or (deck.kind != 'textbook' and deck.owner_id != user_id):
            raise ApplicationError('deck_not_found', 'Deck not found', 404)
        if write and deck.kind == 'textbook':
            raise ApplicationError('readonly_deck', 'Textbook decks are read-only', 403)
        return deck

    def _card(self, tx, user_id, card_id, write=False):
        card = tx.card(card_id)
        if card is None:
            raise ApplicationError('card_not_found', 'Card not found', 404)
        self._deck(tx, user_id, card.deck_id, write)
        return card

    @staticmethod
    def _deck_view(tx, deck):
        return Deck(id=deck.id, name=deck.name, kind=deck.kind, unit_number=deck.unit_number, card_count=len(tx.cards(deck.id)))

    @staticmethod
    def _card_view(tx, user_id, card):
        state = tx.state(user_id, card.id)
        values = {name: getattr(card, name) for name in ('id', 'deck_id', 'word', 'meaning', 'example', 'notes', 'image_url', 'ipa', 'pos', 'source_fragment_id', 'unit_number', 'page', 'audio_url')}
        if card.unit_number is not None and card.page is not None:
            values['source_label'] = f'[Unit {card.unit_number}, Page {card.page}]'
        if state:
            values.update(difficult=state.difficult, due_at=utc(state.due_at) if state.due_at else None, review_count=state.review_count)
        return Card(**values)

    @staticmethod
    def _text(value, field, limit, required=False):
        if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
            raise ApplicationError('invalid_flashcard', f'Invalid {field}', 422)
        return value.strip()

    @staticmethod
    def _duplicate(tx, deck_id, word, exclude=None):
        if any(card.normalized_word == normalize_word(word) and card.id != exclude for card in tx.cards(deck_id)):
            raise ApplicationError('duplicate_word', 'This word already exists in the deck', 409)

    def list_decks(self, user_id):
        with self.repository.transaction() as tx:
            return [self._deck_view(tx, deck) for deck in tx.decks(user_id)]

    def create_deck(self, user_id, name):
        name = self._text(name, 'name', 200, True)
        with self.repository.transaction() as tx:
            return self._deck_view(tx, tx.create_deck(owner_id=user_id, name=name, kind='personal'))

    def update_deck(self, user_id, deck_id, name):
        with self.repository.transaction() as tx:
            deck = self._deck(tx, user_id, deck_id, True)
            deck.name = self._text(name, 'name', 200, True)
            return self._deck_view(tx, deck)

    def delete_deck(self, user_id, deck_id):
        with self.repository.transaction() as tx:
            tx.delete_deck(self._deck(tx, user_id, deck_id, True))

    def get_card(self, user_id, card_id):
        with self.repository.transaction() as tx:
            return self._card_view(tx, user_id, self._card(tx, user_id, card_id))

    def list_cards(self, user_id, deck_id):
        with self.repository.transaction() as tx:
            deck = self._deck(tx, user_id, deck_id)
            cards = tx.cards(deck_id)
            missing = (
                [(card.id, card.word) for card in cards if not card.ipa]
                if deck.kind == 'personal'
                else []
            )
        for card_id, word in missing:
            ipa = self._pronunciation(word)
            if not ipa:
                continue
            with self.repository.transaction() as tx:
                card = self._card(tx, user_id, card_id, True)
                if card.word == word and not card.ipa:
                    card.ipa = ipa
        with self.repository.transaction() as tx:
            self._deck(tx, user_id, deck_id)
            return [self._card_view(tx, user_id, card) for card in tx.cards(deck_id)]

    def create_card(self, user_id, deck_id, *, word, meaning, example='', notes='', image_url=None, source_card_id=None):
        values = self._content(dict(word=word, meaning=meaning, example=example, notes=notes, image_url=image_url))
        if source_card_id is None:
            values['ipa'] = self._pronunciation(values['word'])
        with self.repository.transaction() as tx:
            self._deck(tx, user_id, deck_id, True)
            self._duplicate(tx, deck_id, values['word'])
            if source_card_id:
                source = self._card(tx, user_id, source_card_id)
                # A citation supports the saved content only while its grounded fields agree.
                if normalize_word(values['word']) == source.normalized_word and values['meaning'] == source.meaning and values['example'] == source.example:
                    values.update({key: getattr(source, key) for key in ('source_fragment_id', 'unit_number', 'page', 'ipa', 'pos', 'audio_url')})
            return self._card_view(tx, user_id, tx.create_card(deck_id=deck_id, normalized_word=normalize_word(values['word']), **values))

    def _content(self, values):
        for field, limit in (('word', 200), ('meaning', 1000), ('example', 4000), ('notes', 4000)):
            if field in values:
                values[field] = self._text(values[field], field, limit, field in ('word', 'meaning'))
        if 'image_url' in values and values['image_url'] is not None:
            url = self._text(values['image_url'], 'image_url', 2048)
            if not url.startswith(('https://', 'http://')):
                raise ApplicationError('invalid_flashcard', 'Image URL must use HTTP or HTTPS', 422)
            values['image_url'] = url
        return values

    def update_card(self, user_id, card_id, **values):
        if set(values) - {'word', 'meaning', 'example', 'notes', 'image_url', 'deck_id'}:
            raise ApplicationError('invalid_flashcard', 'Unsupported card fields', 422)
        values = self._content(values)
        generated_ipa = (
            self._pronunciation(values['word']) if 'word' in values else None
        )
        with self.repository.transaction() as tx:
            card = self._card(tx, user_id, card_id, True)
            target = values.get('deck_id', card.deck_id)
            self._deck(tx, user_id, target, True)
            self._duplicate(tx, target, values.get('word', card.word), card.id)
            if any(field in values and values[field] != getattr(card, field) for field in ('word', 'meaning', 'example')):
                for field in ('source_fragment_id', 'unit_number', 'page', 'ipa', 'pos', 'audio_url'):
                    setattr(card, field, None)
                state = tx.state(user_id, card_id)
                if state:
                    state.due_at = None
                    state.review_count = 0
                    state.successful_reviews = 0
            for field, value in values.items():
                setattr(card, field, value)
            if 'word' in values:
                card.ipa = generated_ipa
            card.normalized_word = normalize_word(card.word)
            return self._card_view(tx, user_id, card)

    def delete_card(self, user_id, card_id):
        with self.repository.transaction() as tx:
            tx.delete_card(self._card(tx, user_id, card_id, True))

    def flag(self, user_id, card_id, difficult):
        with self.repository.transaction() as tx:
            card = self._card(tx, user_id, card_id)
            tx.state(user_id, card_id, create=True).difficult = difficult
            return self._card_view(tx, user_id, card)

    def _all_cards(self, tx, user_id, deck_id=None):
        decks = [self._deck(tx, user_id, deck_id)] if deck_id else tx.decks(user_id)
        return [self._card_view(tx, user_id, card) for deck in decks for card in tx.cards(deck.id)]

    def review_queue(self, user_id, deck_id=None):
        now = utc(self.clock())
        with self.repository.transaction() as tx:
            cards = self._all_cards(tx, user_id, deck_id)
            due = sorted((c for c in cards if c.due_at is not None and c.due_at <= now), key=lambda c: c.due_at)
            new = [c for c in cards if c.due_at is None][:5]
            return (due + new)[:20]

    def review(self, user_id, card_id, *, request_id: UUID, answer: str, rating: str):
        if rating not in ('again', 'hard', 'good'):
            raise ApplicationError('invalid_rating', 'Invalid recall rating', 422)
        answer = self._text(answer, 'answer', 200)
        digest = hashlib.sha256(json.dumps([str(card_id), answer, rating], ensure_ascii=False).encode()).hexdigest()
        now = utc(self.clock())
        with self.repository.transaction() as tx:
            card = self._card(tx, user_id, card_id)
            existing = tx.review(user_id, request_id)
            if existing:
                if existing.payload_hash != digest:
                    raise ApplicationError('idempotency_conflict', 'Request ID was used with different content', 409)
                return ReviewResult(**existing.result)
            state = tx.state(user_id, card_id, create=True)
            # SQL Server's update/range lock on state serializes this card's
            # reviews. A concurrent identical request may have committed while
            # this transaction waited for that lock.
            existing = tx.review(user_id, request_id)
            if existing:
                if existing.payload_hash != digest:
                    raise ApplicationError('idempotency_conflict', 'Request ID was used with different content', 409)
                return ReviewResult(**existing.result)
            correct = normalize_word(answer) == card.normalized_word
            if not correct or rating == 'again':
                interval = timedelta(minutes=10)
                state.successful_reviews = 0
            elif rating == 'hard':
                interval = timedelta(hours=6)
            else:
                interval = timedelta(days=min(30, 2 ** min(state.successful_reviews, 5)))
                # Repeated immediate submissions never build multiple successful sessions.
                if state.due_at is None or utc(state.due_at) <= now:
                    state.successful_reviews += 1
            if correct and rating == 'good' and state.due_at and utc(state.due_at) > now:
                due_at = utc(state.due_at)
            else:
                due_at = now + interval
            state.due_at = due_at
            state.review_count += 1
            result = ReviewResult(correct=correct, meaning=card.meaning, due_at=due_at)
            snapshot = result.model_dump(mode='json')
            snapshot.update(
                prompt=card.word,
                answer=answer,
                rating=rating,
                scheduling_version='recall-v1',
            )
            tx.create_review(user_id=user_id, card_id=card_id, request_id=request_id, payload_hash=digest, result=snapshot, created_at=now)
            return result

    def progress(self, user_id):
        now = utc(self.clock())
        with self.repository.transaction() as tx:
            cards = self._all_cards(tx, user_id)
            return dict(reviewed_cards=sum(c.review_count > 0 for c in cards), due_cards=sum(c.due_at is None or c.due_at <= now for c in cards), difficult_cards=sum(c.difficult for c in cards))
