from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.api.errors import ApplicationError
from english7.db.base import Base
from english7.db.models import Role, User


@pytest.fixture
def setup():
    from english7.modules.flashcards.repository import SQLAlchemyFlashcardRepository
    from english7.modules.flashcards.service import FlashcardService

    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', lambda conn, _: conn.execute('PRAGMA foreign_keys=ON'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users = [uuid4(), uuid4()]
    with factory.begin() as session:
        role = Role(name='student')
        session.add(role)
        session.flush()
        session.add_all(User(id=uid, email=f'{uid}@example.com', password_hash='test', role_id=role.id) for uid in users)
    now = [datetime(2026, 9, 25, tzinfo=timezone.utc)]
    service = FlashcardService(SQLAlchemyFlashcardRepository(factory), clock=lambda: now[0])
    return service, users, now, factory


def test_private_crud_duplicate_and_move(setup):
    service, (owner, stranger), _, _ = setup
    deck = service.create_deck(owner, 'My words')
    card = service.create_card(owner, deck.id, word=' Collect ', meaning='sưu tầm')
    assert card.word == 'Collect'
    assert service.list_decks(stranger) == []
    for operation in [lambda: service.get_card(stranger, card.id), lambda: service.update_deck(stranger, deck.id, 'stolen'), lambda: service.delete_card(stranger, card.id)]:
        with pytest.raises(ApplicationError) as error:
            operation()
        assert error.value.status_code == 404
    with pytest.raises(ApplicationError) as duplicate:
        service.create_card(owner, deck.id, word='collect', meaning='trùng')
    assert duplicate.value.status_code == 409
    target = service.create_deck(owner, 'New deck')
    moved = service.update_card(owner, card.id, deck_id=target.id, notes='practice')
    assert moved.deck_id == target.id
    assert service.list_cards(owner, deck.id) == []
    service.delete_deck(owner, target.id)
    with pytest.raises(ApplicationError):
        service.get_card(owner, card.id)


def test_personal_card_automatically_receives_ai_pronunciation(setup):
    from english7.modules.flashcards.service import FlashcardService

    class Pronouncer:
        def __init__(self):
            self.words = []

        def pronounce(self, text):
            self.words.append(text)
            return "/həˈloʊ/"

    existing, (owner, _), now, _ = setup
    pronouncer = Pronouncer()
    service = FlashcardService(
        existing.repository,
        clock=lambda: now[0],
        pronunciation_provider=pronouncer,
    )
    deck = service.create_deck(owner, "Personal")

    card = service.create_card(owner, deck.id, word="hello", meaning="xin chào")

    assert card.ipa == "/həˈloʊ/"
    assert pronouncer.words == ["hello"]


def test_editing_personal_card_word_refreshes_ai_pronunciation(setup):
    from english7.modules.flashcards.service import FlashcardService

    class Pronouncer:
        def pronounce(self, text):
            return {"hello": "/həˈloʊ/", "benefit": "/ˈbenɪfɪt/"}[text]

    existing, (owner, _), now, _ = setup
    service = FlashcardService(
        existing.repository,
        clock=lambda: now[0],
        pronunciation_provider=Pronouncer(),
    )
    deck = service.create_deck(owner, "Personal")
    card = service.create_card(owner, deck.id, word="hello", meaning="xin chào")

    updated = service.update_card(owner, card.id, word="benefit")

    assert updated.ipa == "/ˈbenɪfɪt/"


def test_listing_personal_cards_backfills_missing_ai_pronunciation(setup):
    from english7.modules.flashcards.service import FlashcardService

    class Pronouncer:
        def __init__(self):
            self.words = []

        def pronounce(self, text):
            self.words.append(text)
            return "/həˈloʊ/"

    existing, (owner, _), now, _ = setup
    deck = existing.create_deck(owner, "Personal")
    card = existing.create_card(owner, deck.id, word="hello", meaning="xin chào")
    assert card.ipa is None

    pronouncer = Pronouncer()
    service = FlashcardService(
        existing.repository,
        clock=lambda: now[0],
        pronunciation_provider=pronouncer,
    )

    assert service.list_cards(owner, deck.id)[0].ipa == "/həˈloʊ/"
    assert service.list_cards(owner, deck.id)[0].ipa == "/həˈloʊ/"
    assert pronouncer.words == ["hello"]


def test_temporary_ai_failure_does_not_block_card_creation_and_retries(setup):
    from english7.modules.ai.contracts import AIProviderError
    from english7.modules.flashcards.service import FlashcardService

    class FlakyPronouncer:
        def __init__(self):
            self.calls = 0

        def pronounce(self, text):
            self.calls += 1
            if self.calls == 1:
                raise AIProviderError("ai_provider_failed")
            return "/həˈloʊ/"

    existing, (owner, _), now, _ = setup
    pronouncer = FlakyPronouncer()
    service = FlashcardService(
        existing.repository,
        clock=lambda: now[0],
        pronunciation_provider=pronouncer,
    )
    deck = service.create_deck(owner, "Personal")

    created = service.create_card(
        owner,
        deck.id,
        word="hello",
        meaning="xin chào",
    )

    assert created.ipa is None
    assert service.list_cards(owner, deck.id)[0].ipa == "/həˈloʊ/"
    assert pronouncer.calls == 2


def test_review_recall_schedule_and_idempotency(setup):
    service, (owner, _), now, _ = setup
    deck = service.create_deck(owner, 'Words')
    card = service.create_card(owner, deck.id, word='collect', meaning='sưu tầm')
    assert len(service.review_queue(owner)) == 1
    request = uuid4()
    wrong = service.review(owner, card.id, request_id=request, answer='sưu tầm', rating='good')
    assert not wrong.correct
    assert wrong.due_at == now[0] + timedelta(minutes=10)
    assert service.review(owner, card.id, request_id=request, answer='sưu tầm', rating='good') == wrong
    with pytest.raises(ApplicationError) as error:
        service.review(owner, card.id, request_id=request, answer='collect', rating='good')
    assert error.value.status_code == 409
    assert service.get_card(owner, card.id).review_count == 1
    assert service.review_queue(owner) == []
    now[0] += timedelta(minutes=10)
    correct = service.review(owner, card.id, request_id=uuid4(), answer=' COLLECT ', rating='good')
    assert correct.correct
    assert correct.due_at == now[0] + timedelta(days=1)
    service.flag(owner, card.id, True)
    assert service.progress(owner) == {'reviewed_cards': 1, 'due_cards': 0, 'difficult_cards': 1}


def test_public_cards_readonly_and_copy_provenance(setup):
    from english7.modules.flashcards.models import FlashcardDeck, Flashcard
    service, (owner, stranger), _, factory = setup
    with factory.begin() as session:
        deck = FlashcardDeck(name='Unit 1', kind='textbook', unit_number=1)
        session.add(deck)
        session.flush()
        card = Flashcard(deck_id=deck.id, word='collect', normalized_word='collect', meaning='sưu tầm', unit_number=1, page=9)
        session.add(card)
        session.flush()
        deck_id, card_id = deck.id, card.id
    assert service.list_decks(stranger)[0].kind == 'textbook'
    for operation in [lambda: service.delete_deck(owner, deck_id), lambda: service.update_card(owner, card_id, meaning='bad'), lambda: service.create_card(owner, deck_id, word='bad', meaning='bad')]:
        with pytest.raises(ApplicationError) as error:
            operation()
        assert error.value.status_code == 403
    personal = service.create_deck(owner, 'Saved')
    copy = service.create_card(owner, personal.id, word='collect', meaning='sưu tầm', source_card_id=card_id)
    assert copy.source_label == '[Unit 1, Page 9]'
    changed = service.update_card(owner, copy.id, word='other')
    assert changed.source_label == 'Personal card'
    assert changed.page is None
    service.flag(owner, card_id, True)
    assert not service.get_card(stranger, card_id).difficult


def test_router_allows_students_and_admins_to_manage_personal_cards(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from english7.api.errors import install_error_handling
    from english7.modules.auth.domain import AuthUser
    from english7.modules.auth.router import get_current_user
    from english7.modules.flashcards.router import router, get_flashcard_service

    service, (owner, _), _, _ = setup
    app = FastAPI()
    install_error_handling(app)
    app.include_router(router, prefix='/api/v1')
    app.dependency_overrides[get_flashcard_service] = lambda: service
    with TestClient(app) as client:
        assert client.get('/api/v1/flashcards/decks').status_code == 401
        app.dependency_overrides[get_current_user] = lambda: AuthUser(owner, 'test@example.com', 'unused', 'admin')
        admin_deck = client.post('/api/v1/flashcards/decks', json={'name': 'Admin deck'})
        assert admin_deck.status_code == 201
        admin_card = client.post(
            f'/api/v1/flashcards/decks/{admin_deck.json()["id"]}/cards',
            json={'word': 'manage', 'meaning': 'quản lý'},
        )
        assert admin_card.status_code == 201
        app.dependency_overrides[get_current_user] = lambda: AuthUser(owner, 'test@example.com', 'unused', 'student')
        deck = client.post('/api/v1/flashcards/decks', json={'name': 'My deck'})
        assert deck.status_code == 201
        deck_id = deck.json()['id']
        card = client.post(f'/api/v1/flashcards/decks/{deck_id}/cards', json={'word': 'hobby', 'meaning': 'sở thích'})
        assert card.status_code == 201
        card_id = card.json()['id']
        assert card.json()['source_label'] == 'Personal card'
        review_ids = {
            item['id'] for item in client.get('/api/v1/flashcards/review').json()['items']
        }
        assert card_id in review_ids
        assert client.patch(f'/api/v1/flashcards/cards/{card_id}', json={'word': None}).status_code == 422
        assert client.patch(f'/api/v1/flashcards/cards/{card_id}', json={'page': 88}).status_code == 422
        reviewed = client.post(f'/api/v1/flashcards/cards/{card_id}/review', json={'request_id': str(uuid4()), 'answer': 'HOBBY', 'rating': 'good'})
        assert reviewed.status_code == 200
        assert reviewed.json()['correct'] is True
        assert client.delete(f'/api/v1/flashcards/cards/{card_id}').status_code == 204


def test_seed_requires_verified_real_pages_and_exact_word_evidence(setup):
    from english7.db.models import Textbook, Unit, Section, Activity, SourceDocument, SourceFragment
    from english7.modules.flashcards.seed import seed_textbook_flashcards
    service, (owner, _), _, factory = setup
    with factory.begin() as session:
        book = Textbook(title='English 7')
        session.add(book)
        session.flush()
        unit = Unit(textbook_id=book.id, number=1, title='Hobbies', is_published=True)
        doc = SourceDocument(textbook_id=book.id, original_filename='book.pdf', object_key='book', file_hash='hash', page_count=100, ingestion_version='test')
        session.add_all([unit, doc])
        session.flush()
        section = Section(unit_id=unit.id, title='Words', section_type='vocabulary', position=1)
        session.add(section)
        session.flush()
        activity = Activity(section_id=section.id, activity_type='vocabulary')
        session.add(activity)
        session.flush()
        for page, status, text in [(9, 'verified', 'My hobby is reading.'), (10, 'draft', 'pottery'), (None, 'verified', 'pottery'), (11, 'verified', 'potterymaking')]:
            session.add(SourceFragment(source_document_id=doc.id, activity_id=activity.id, pdf_page=5, printed_page=page, x=0, y=0, width=1, height=1, normalized_text=text, review_status=status, is_published=status == 'verified'))
    assert seed_textbook_flashcards(factory) == 1
    assert seed_textbook_flashcards(factory) == 0
    deck = service.list_decks(owner)[0]
    card = service.list_cards(owner, deck.id)[0]
    assert card.word == 'hobby'
    assert card.source_label == '[Unit 1, Page 9]'
    assert card.source_fragment_id is not None
    assert card.example == ''  # Ontology examples are not asserted as textbook quotations.
    assert card.audio_url is None


def test_again_shortens_schedule_and_edit_resets_old_learning(setup):
    service, (owner, _), now, _ = setup
    deck = service.create_deck(owner, 'Words')
    card = service.create_card(owner, deck.id, word='hobby', meaning='sở thích')
    service.review(owner, card.id, request_id=uuid4(), answer='hobby', rating='good')
    repeated = service.review(owner, card.id, request_id=uuid4(), answer='hobby', rating='good')
    assert repeated.due_at == now[0] + timedelta(days=1)
    again = service.review(owner, card.id, request_id=uuid4(), answer='hobby', rating='again')
    assert again.due_at == now[0] + timedelta(minutes=10)
    edited = service.update_card(owner, card.id, word='pottery')
    assert edited.review_count == 0
    assert edited.due_at is None


def test_new_card_budget_and_due_reviews_take_priority(setup):
    service, (owner, _), now, _ = setup
    deck = service.create_deck(owner, 'Words')
    cards = [service.create_card(owner, deck.id, word=f'word {i}', meaning='từ') for i in range(25)]
    assert len(service.review_queue(owner)) == 5
    for card in cards[:21]:
        service.review(owner, card.id, request_id=uuid4(), answer=card.word, rating='good')
    now[0] += timedelta(days=1)
    queue = service.review_queue(owner)
    assert len(queue) == 20
    assert all(card.review_count == 1 for card in queue)


def test_move_duplicate_rolls_back_and_foreign_destination_is_hidden(setup):
    service, (owner, other), _, _ = setup
    deck = service.create_deck(owner, 'First')
    target = service.create_deck(owner, 'Second')
    foreign = service.create_deck(other, 'Hidden')
    card = service.create_card(owner, deck.id, word='hobby', meaning='sở thích')
    service.create_card(owner, target.id, word='HOBBY', meaning='sở thích')
    with pytest.raises(ApplicationError) as duplicate:
        service.update_card(owner, card.id, deck_id=target.id)
    assert duplicate.value.status_code == 409
    assert service.get_card(owner, card.id).deck_id == deck.id
    with pytest.raises(ApplicationError) as hidden:
        service.update_card(owner, card.id, deck_id=foreign.id)
    assert hidden.value.status_code == 404


def test_seed_query_uses_sql_server_bit_comparison(setup):
    from sqlalchemy.dialects import mssql
    service, _, _, factory = setup
    compiled = []

    def capture(_connection, statement, _multiparams, _params, _options):
        compiled.append(str(statement.compile(dialect=mssql.dialect())))

    engine = factory.kw['bind']
    event.listen(engine, 'before_execute', capture)
    try:
        with service.repository.transaction() as tx:
            assert tx.verified_sources() == []
    finally:
        event.remove(engine, 'before_execute', capture)
    query = compiled[-1]
    assert 'units.is_published = 1' in query
    assert 'source_fragments.is_published = 1' in query
    assert ' IS 1' not in query


def test_review_history_keeps_content_and_scheduler_snapshot_after_edit(setup):
    from sqlalchemy import select
    from english7.modules.flashcards.models import FlashcardReview

    service, (owner, _), _, factory = setup
    deck = service.create_deck(owner, 'Words')
    card = service.create_card(owner, deck.id, word='hobby', meaning='sở thích')
    request_id = uuid4()
    result = service.review(owner, card.id, request_id=request_id, answer='HOBBY', rating='good')
    service.update_card(owner, card.id, word='pottery', meaning='đồ gốm')
    with factory() as session:
        record = session.scalar(select(FlashcardReview).where(FlashcardReview.request_id == request_id))
        assert record.result['prompt'] == 'hobby'
        assert record.result['meaning'] == 'sở thích'
        assert record.result['answer'] == 'HOBBY'
        assert record.result['rating'] == 'good'
        assert record.result['scheduling_version'] == 'recall-v1'
    assert service.review(owner, card.id, request_id=request_id, answer='HOBBY', rating='good') == result
    assert set(result.model_dump()) == {'correct', 'meaning', 'due_at'}
