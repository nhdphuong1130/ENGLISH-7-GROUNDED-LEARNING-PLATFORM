from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from english7.api.errors import ApplicationError
from english7.db.session import get_session_factory
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.flashcards.domain import Card, Deck, ReviewResult
from english7.modules.flashcards.repository import SQLAlchemyFlashcardRepository
from english7.modules.flashcards.service import FlashcardService


router = APIRouter(prefix='/flashcards', tags=['flashcards'])


def require_student(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    if user.role != 'student':
        raise ApplicationError('forbidden', 'Student role is required', 403)
    return user


def get_flashcard_service(request: Request) -> FlashcardService:
    from pathlib import Path
    from english7.core.settings import get_settings
    from english7.modules.flashcards.audio_cache import VocabAudioCache
    from english7.modules.speaking.runtime import LocalSpeechRuntime

    settings = get_settings()
    cache_dir = Path(settings.vocab_audio_cache_dir) if settings.vocab_audio_cache_dir else (Path(__file__).resolve().parents[5] / "speech" / ".cache" / "vocab_audio")
    audio_cache = VocabAudioCache(
        cache_dir=cache_dir,
        runtime=LocalSpeechRuntime(settings.speech_runtime_url, settings.speech_timeout_seconds),
    )
    return FlashcardService(
        SQLAlchemyFlashcardRepository(get_session_factory()),
        audio_cache=audio_cache,
        pronunciation_provider=getattr(
            request.app.state, "pronunciation_provider", None
        ),
    )


Student = Annotated[AuthUser, Depends(require_student)]
Service = Annotated[FlashcardService, Depends(get_flashcard_service)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class DeckInput(Input):
    name: str = Field(min_length=1, max_length=200)


class CardInput(Input):
    word: str = Field(min_length=1, max_length=200)
    meaning: str = Field(min_length=1, max_length=1000)
    example: str = Field(default='', max_length=4000)
    notes: str = Field(default='', max_length=4000)
    image_url: str | None = Field(default=None, max_length=2048)
    source_card_id: UUID | None = None


class CardUpdate(Input):
    word: str | None = Field(default=None, min_length=1, max_length=200)
    meaning: str | None = Field(default=None, min_length=1, max_length=1000)
    example: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, max_length=2048)
    deck_id: UUID | None = None


class ReviewInput(Input):
    request_id: UUID
    answer: str = Field(max_length=200)
    rating: Literal['again', 'hard', 'good']


class FlagInput(Input):
    difficult: bool


@router.get('/decks')
def decks(user: Student, service: Service) -> dict[str, list[Deck]]:
    return {'items': service.list_decks(user.id)}


@router.post('/decks', status_code=201)
def create_deck(payload: DeckInput, user: Student, service: Service) -> Deck:
    return service.create_deck(user.id, payload.name)


@router.patch('/decks/{deck_id}')
def update_deck(deck_id: UUID, payload: DeckInput, user: Student, service: Service) -> Deck:
    return service.update_deck(user.id, deck_id, payload.name)


@router.delete('/decks/{deck_id}', status_code=204)
def delete_deck(deck_id: UUID, user: Student, service: Service) -> Response:
    service.delete_deck(user.id, deck_id)
    return Response(status_code=204)


@router.get('/decks/{deck_id}/cards')
def cards(deck_id: UUID, user: Student, service: Service) -> dict[str, list[Card]]:
    return {'items': service.list_cards(user.id, deck_id)}


@router.post('/decks/{deck_id}/cards', status_code=201)
def create_card(deck_id: UUID, payload: CardInput, user: Student, service: Service) -> Card:
    return service.create_card(user.id, deck_id, **payload.model_dump())


@router.patch('/cards/{card_id}')
def update_card(card_id: UUID, payload: CardUpdate, user: Student, service: Service) -> Card:
    return service.update_card(user.id, card_id, **payload.model_dump(exclude_unset=True))


@router.delete('/cards/{card_id}', status_code=204)
def delete_card(card_id: UUID, user: Student, service: Service) -> Response:
    service.delete_card(user.id, card_id)
    return Response(status_code=204)


@router.get('/review')
def review_queue(user: Student, service: Service, deck_id: UUID | None = None) -> dict[str, list[Card]]:
    return {'items': service.review_queue(user.id, deck_id)}


@router.post('/cards/{card_id}/review')
def review(card_id: UUID, payload: ReviewInput, user: Student, service: Service) -> ReviewResult:
    return service.review(user.id, card_id, **payload.model_dump())


@router.patch('/cards/{card_id}/flag')
def flag(card_id: UUID, payload: FlagInput, user: Student, service: Service) -> Card:
    return service.flag(user.id, card_id, payload.difficult)


@router.get('/cards/{card_id}/audio')
def card_audio(card_id: UUID, user: Student, service: Service) -> Response:
    audio_bytes = service.card_audio(user.id, card_id)
    return Response(content=audio_bytes, media_type='audio/wav', headers={'Cache-Control': 'public, max-age=86400'})
