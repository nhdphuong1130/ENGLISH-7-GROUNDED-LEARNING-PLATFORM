from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.db.base import Base
from english7.db.models import Role, User
from english7.main import app
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.flashcards.router import get_flashcard_service
from english7.modules.flashcards.repository import SQLAlchemyFlashcardRepository
from english7.modules.flashcards.service import FlashcardService
from english7.modules.speaking.router import get_speaking_service
from english7.modules.speaking.repository import SpeakingRepository
from english7.modules.speaking.service import SpeakingService
from english7.api.errors import ApplicationError


class Runtime:
    offline = False
    calls = 0

    def voices(self):
        if self.offline:
            raise ApplicationError('unavailable', 'Unavailable', 503)
        return [{'id': 'test-voice', 'name': 'Test'}]

    def transcribe(self, audio):
        self.calls += 1
        return {'transcript': 'reading', 'model': 'test'}

    def synthesize(self, text, voice_id):
        return b'RIFF-test'


@pytest.fixture
def learning(tmp_path):
    from english7.modules.flashcards.audio_cache import VocabAudioCache

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    user = AuthUser.new(email='learning@example.com', password_hash='x', role='student')
    with factory.begin() as session:
        role = Role(name='student')
        session.add(role)
        session.flush()
        session.add(User(id=user.id, email=user.email, password_hash='x', role_id=role.id))
    runtime = Runtime()
    audio_cache = VocabAudioCache(tmp_path / 'vocab_audio', runtime=runtime)
    cards = FlashcardService(SQLAlchemyFlashcardRepository(factory), audio_cache=audio_cache)
    from english7.modules.admin.router import get_admin_speaking_service
    speech = SpeakingService(SpeakingRepository(factory), cards, runtime)
    app.dependency_overrides[get_flashcard_service] = lambda: cards
    app.dependency_overrides[get_speaking_service] = lambda: speech
    app.dependency_overrides[get_admin_speaking_service] = lambda: speech
    app.dependency_overrides[get_current_user] = lambda: user
    yield runtime
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize('path', ['/flashcards/decks', '/learning/progress', '/speaking/voices', '/speaking/history'])
def test_learning_routes_require_auth(client, path):
    assert client.get('/api/v1' + path).status_code == 401


def test_learning_flow_persists_reviews_and_speech(client, learning):
    deck = client.post('/api/v1/flashcards/decks', json={'name': 'My words'})
    assert deck.status_code == 201
    card = client.post(f'/api/v1/flashcards/decks/{deck.json()["id"]}/cards',
                       json={'word': 'reading', 'meaning': 'đọc sách'})
    assert card.status_code == 201
    card_id = card.json()['id']
    review = client.post(f'/api/v1/flashcards/cards/{card_id}/review',
                         json={'request_id': str(uuid4()), 'answer': 'reading', 'rating': 'good'})
    assert review.status_code == 200
    request_id = uuid4()
    url = f'/api/v1/speaking/attempts/{request_id}?card_id={card_id}&voice_id=test-voice'
    result = client.post(url, files={'audio': ('recording.wav', b'recording', 'audio/wav')})
    assert result.status_code == 200
    assert result.json()['transcript'] == 'reading'
    assert result.json()['match_percent'] == 100
    assert client.post(url, files={'audio': ('recording.wav', b'recording', 'audio/wav')}).json() == result.json()
    assert learning.calls == 1
    progress = client.get('/api/v1/learning/progress').json()
    assert progress['reviewed_cards'] == 1
    assert progress['speaking_count'] == 1
    assert progress['recent_speaking'] == [result.json()]
    audio = client.post(f'/api/v1/speaking/attempts/{request_id}/audio')
    assert audio.content == b'RIFF-test'
    assert audio.headers['cache-control'] == 'no-store'


def test_offline_speech_does_not_disable_flashcards(client, learning):
    learning.offline = True
    assert client.get('/api/v1/speaking/voices').json()['available'] is False
    assert client.get('/api/v1/flashcards/decks').status_code == 200
    assert client.get('/api/v1/learning/progress').status_code == 200


def test_admin_cannot_access_student_learning(client, learning):
    app.dependency_overrides[get_current_user] = lambda: AuthUser.new(
        email='admin@example.com', password_hash='x', role='admin')
    for path in ['/flashcards/decks', '/learning/progress', '/speaking/voices', '/speaking/history']:
        assert client.get('/api/v1' + path).status_code == 403
    assert client.get('/api/v1/admin/speaking/voices').status_code == 200
    assert client.get('/api/v1/admin/speaking/history').status_code == 200


def test_admin_can_use_speaking_practice(client, learning):
    from unittest.mock import MagicMock
    from english7.modules.flashcards.domain import Card

    admin = AuthUser.new(email='admin@example.com', password_hash='x', role='admin')
    app.dependency_overrides[get_current_user] = lambda: admin

    card_id = uuid4()
    cards_service = app.dependency_overrides[get_flashcard_service]()
    cards_service.get_card = MagicMock(return_value=Card(
        id=card_id, deck_id=uuid4(), word='reading', meaning='đọc sách',
        example='He likes reading books.', source_label='[Unit 1, Page 10]'
    ))

    # 1. Preview
    res_prev = client.post('/api/v1/admin/speaking/preview', json={'voice_id': 'test-voice'})
    assert res_prev.status_code == 200
    assert res_prev.content == b'RIFF-test'

    # 2. Select voice
    res_set = client.put('/api/v1/admin/speaking/voice', json={'voice_id': 'test-voice'})
    assert res_set.status_code == 200

    # 3. Submit speaking attempt
    request_id = uuid4()
    url = f'/api/v1/admin/speaking/attempts/{request_id}?card_id={card_id}&voice_id=test-voice'
    result = client.post(url, files={'audio': ('recording.wav', b'recording', 'audio/wav')})
    assert result.status_code == 200
    assert result.json()['transcript'] == 'reading'

    # 4. Audio feedback
    audio = client.post(f'/api/v1/admin/speaking/attempts/{request_id}/audio')
    assert audio.content == b'RIFF-test'


def test_oversized_speech_rejected_before_auth_and_multipart_parsing(client, monkeypatch):
    from starlette.requests import Request
    called = []
    original = Request.form

    def form(self, *args, **kwargs):
        called.append(True)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Request, 'form', form)
    response = client.post(f'/api/v1/speaking/attempts/{uuid4()}?card_id={uuid4()}&voice_id=test',
                           files={'audio': ('recording.wav', b'x' * (3 * 1024 * 1024), 'audio/wav')})
    assert response.status_code == 413
    assert called == []


def test_flashcard_card_audio_endpoint(client, learning):
    deck = client.post('/api/v1/flashcards/decks', json={'name': 'Audio Deck'}).json()
    card = client.post(f'/api/v1/flashcards/decks/{deck["id"]}/cards',
                       json={'word': 'community', 'meaning': 'cộng đồng'}).json()
    card_id = card['id']

    # Initial fetch (cache miss -> synthesizes)
    response = client.get(f'/api/v1/flashcards/cards/{card_id}/audio')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'audio/wav'
    assert response.content == b'RIFF-test'
    assert 'public, max-age=86400' in response.headers['cache-control']

    # Second fetch (cache hit -> reads from disk)
    response2 = client.get(f'/api/v1/flashcards/cards/{card_id}/audio')
    assert response2.status_code == 200
    assert response2.content == b'RIFF-test'

    # Non-existent card returns 404
    missing_response = client.get(f'/api/v1/flashcards/cards/{uuid4()}/audio')
    assert missing_response.status_code == 404
