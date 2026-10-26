from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from english7.db.session import get_session_factory
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.admin.dependencies import AdminUser
from english7.modules.admin.practice_service import AdminPracticeService


router = APIRouter(prefix="/practice", tags=["admin-practice"])


def get_admin_practice_service(request: Request) -> AdminPracticeService:
    factory = get_session_factory()
    return AdminPracticeService(factory, AdminAuditService(factory), getattr(request.app.state, "pronunciation_provider", None))


PracticeService = Annotated[AdminPracticeService, Depends(get_admin_practice_service)]


def _context(request: Request) -> dict[str, str | None]:
    return {"request_id": getattr(request.state, "trace_id", None), "ip_address": request.client.host if request.client else None, "platform": request.headers.get("x-client-platform")}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionInput(Input):
    expected_version: int = Field(ge=1)


class BlueprintCreate(Input):
    name: str = Field(min_length=1, max_length=255)
    duration_minutes: int = Field(ge=1, le=240)
    difficulty: str = Field(min_length=1, max_length=30)
    policy: dict[str, Any] = Field(default_factory=dict)


class BlueprintUpdate(Input):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    duration_minutes: int | None = Field(default=None, ge=1, le=240)
    difficulty: str | None = Field(default=None, min_length=1, max_length=30)
    policy: dict[str, Any] | None = None


class DeckCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    unit_id: UUID


class DeckUpdate(Input):
    name: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)


class CardCreate(Input):
    word: str = Field(min_length=1, max_length=200)
    meaning: str = Field(min_length=1, max_length=1000)
    source_fragment_id: UUID
    example: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=4000)
    pos: str | None = Field(default=None, max_length=100)


class CardUpdate(Input):
    expected_version: int = Field(ge=1)
    word: str | None = Field(default=None, min_length=1, max_length=200)
    meaning: str | None = Field(default=None, min_length=1, max_length=1000)
    source_fragment_id: UUID | None = None
    example: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)
    pos: str | None = Field(default=None, max_length=100)


class QuestionCreate(Input):
    quiz_id: UUID
    prompt: str = Field(min_length=1)
    question_type: str = Field(min_length=1, max_length=80)
    answer_payload: dict[str, Any]
    source_fragment_ids: list[UUID] = Field(default_factory=list)


class QuestionUpdate(Input):
    expected_version: int = Field(ge=1)
    prompt: str | None = Field(default=None, min_length=1)
    question_type: str | None = Field(default=None, min_length=1, max_length=80)
    answer_payload: dict[str, Any] | None = None
    source_fragment_ids: list[UUID] | None = None


@router.get("/quiz-blueprints")
def list_blueprints(_admin: AdminUser, service: PracticeService): return {"items": service.list_blueprints()}


@router.post("/quiz-blueprints", status_code=201)
def create_blueprint(payload: BlueprintCreate, request: Request, admin: AdminUser, service: PracticeService): return service.create_blueprint(**payload.model_dump(), actor_id=admin.id, **_context(request))


@router.patch("/quiz-blueprints/{item_id}")
def update_blueprint(item_id: UUID, payload: BlueprintUpdate, request: Request, admin: AdminUser, service: PracticeService):
    data = payload.model_dump(exclude_unset=True); expected = data.pop("expected_version"); return service.update_blueprint(item_id, data, expected_version=expected, actor_id=admin.id, **_context(request))


@router.post("/quiz-blueprints/{item_id}/publish")
def publish_blueprint(item_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.set_blueprint_status(item_id, expected_version=payload.expected_version, active=True, actor_id=admin.id, **_context(request))


@router.post("/quiz-blueprints/{item_id}/archive")
def archive_blueprint(item_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.set_blueprint_status(item_id, expected_version=payload.expected_version, active=False, actor_id=admin.id, **_context(request))


@router.delete("/quiz-blueprints/{item_id}", status_code=204)
def delete_blueprint(item_id: UUID, request: Request, admin: AdminUser, service: PracticeService): service.delete_blueprint(item_id, actor_id=admin.id, **_context(request)); return Response(status_code=204)


@router.get("/decks")
def list_decks(_admin: AdminUser, service: PracticeService): return {"items": service.list_decks()}


@router.post("/decks", status_code=201)
def create_deck(payload: DeckCreate, request: Request, admin: AdminUser, service: PracticeService): return service.create_deck(**payload.model_dump(), actor_id=admin.id, **_context(request))


@router.patch("/decks/{deck_id}")
def update_deck(deck_id: UUID, payload: DeckUpdate, request: Request, admin: AdminUser, service: PracticeService): return service.update_deck(deck_id, **payload.model_dump(), actor_id=admin.id, **_context(request))


@router.post("/decks/{deck_id}/publish")
def publish_deck(deck_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.set_deck_status(deck_id, expected_version=payload.expected_version, active=True, actor_id=admin.id, **_context(request))


@router.post("/decks/{deck_id}/archive")
def archive_deck(deck_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.set_deck_status(deck_id, expected_version=payload.expected_version, active=False, actor_id=admin.id, **_context(request))


@router.delete("/decks/{deck_id}", status_code=204)
def delete_deck(deck_id: UUID, request: Request, admin: AdminUser, service: PracticeService): service.delete_deck(deck_id, actor_id=admin.id, **_context(request)); return Response(status_code=204)


@router.get("/decks/{deck_id}/cards")
def list_cards(deck_id: UUID, _admin: AdminUser, service: PracticeService): return {"items": service.list_cards(deck_id)}


@router.post("/decks/{deck_id}/cards", status_code=201)
def create_card(deck_id: UUID, payload: CardCreate, request: Request, admin: AdminUser, service: PracticeService): return service.create_card(deck_id, **payload.model_dump(), actor_id=admin.id, **_context(request))


@router.patch("/cards/{card_id}")
def update_card(card_id: UUID, payload: CardUpdate, request: Request, admin: AdminUser, service: PracticeService):
    data = payload.model_dump(exclude_unset=True); expected = data.pop("expected_version"); return service.update_card(card_id, data, expected_version=expected, actor_id=admin.id, **_context(request))


@router.post("/cards/{card_id}/publish")
def publish_card(card_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.publish_card(card_id, expected_version=payload.expected_version, actor_id=admin.id, **_context(request))


@router.post("/cards/{card_id}/archive")
def archive_card(card_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.archive_card(card_id, expected_version=payload.expected_version, actor_id=admin.id, **_context(request))


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(card_id: UUID, request: Request, admin: AdminUser, service: PracticeService): service.delete_card(card_id, actor_id=admin.id, **_context(request)); return Response(status_code=204)


@router.get("/speaking-prompts")
def speaking_prompts(_admin: AdminUser, service: PracticeService): return {"items": service.list_speaking_prompts()}


@router.get("/questions")
def list_questions(_admin: AdminUser, service: PracticeService, quiz_id: UUID | None = None): return {"items": service.list_questions(quiz_id)}


@router.post("/questions", status_code=201)
def create_question(payload: QuestionCreate, request: Request, admin: AdminUser, service: PracticeService): return service.create_question(**payload.model_dump(), actor_id=admin.id, **_context(request))


@router.patch("/questions/{question_id}")
def update_question(question_id: UUID, payload: QuestionUpdate, request: Request, admin: AdminUser, service: PracticeService):
    data = payload.model_dump(exclude_unset=True); expected = data.pop("expected_version"); return service.update_question(question_id, data, expected_version=expected, actor_id=admin.id, **_context(request))


@router.post("/questions/{question_id}/publish")
def publish_question(question_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.publish_question(question_id, expected_version=payload.expected_version, actor_id=admin.id, **_context(request))


@router.post("/questions/{question_id}/archive")
def archive_question(question_id: UUID, payload: VersionInput, request: Request, admin: AdminUser, service: PracticeService): return service.archive_question(question_id, expected_version=payload.expected_version, actor_id=admin.id, **_context(request))


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: UUID, request: Request, admin: AdminUser, service: PracticeService): service.delete_question(question_id, actor_id=admin.id, **_context(request)); return Response(status_code=204)


@router.post("/{entity_type}/{entity_id}/preview")
def preview(entity_type: Literal["quiz_blueprint", "quiz_question", "flashcard_deck", "flashcard"], entity_id: UUID, _admin: AdminUser, service: PracticeService): return service.preview(entity_type, entity_id)


@router.get("/{entity_type}/{entity_id}/versions")
def versions(entity_type: Literal["quiz_blueprint", "quiz_question", "flashcard_deck", "flashcard"], entity_id: UUID, _admin: AdminUser, service: PracticeService): return {"items": service.versions(entity_type, entity_id)}
