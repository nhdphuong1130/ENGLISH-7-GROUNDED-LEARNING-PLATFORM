from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from english7.api.errors import ApplicationError
from english7.modules.ai.contracts import Language
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user
from english7.modules.ai.contracts import ScopeStatus
from english7.modules.tutor.conversations import ConversationRecord, ExchangeRecord
from english7.modules.tutor.service import TutorAnswer, TutorService

router = APIRouter(prefix="/tutor", tags=["tutor"])


class AskTutorRequest(BaseModel):
    question: str = Field(default="", max_length=2000)
    language: Language
    upload_id: UUID | None = None
    addressing_preference: str | None = Field(default=None, max_length=120)


class CreateConversationRequest(BaseModel):
    title: str = Field(default="Tutor conversation", max_length=160)
    language: Language
    addressing_preference: str | None = Field(default=None, max_length=120)


class CitationResponse(BaseModel):
    fragment_id: UUID
    unit_number: int | None = None
    pdf_page: int
    printed_page: int | None
    image_url: str | None = None


class TutorResponse(BaseModel):
    answer: str
    language: Language
    scope_status: ScopeStatus
    conversation_id: UUID | None = None
    citations: tuple[CitationResponse, ...]


class ConversationSummaryResponse(BaseModel):
    id: UUID
    title: str
    language: Language
    addressing_preference: str | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ExchangeResponse(BaseModel):
    id: UUID
    sequence_number: int
    question: str
    answer: str
    language: Language
    upload_id: UUID | None
    citations: tuple[CitationResponse, ...]
    created_at: datetime


class ConversationDetailResponse(ConversationSummaryResponse):
    exchanges: tuple[ExchangeResponse, ...]


class ConversationListResponse(BaseModel):
    items: tuple[ConversationSummaryResponse, ...]


def get_tutor_service(request: Request) -> TutorService:
    service = getattr(request.app.state, "tutor_service", None)
    if service is None:
        raise ApplicationError(
            "tutor_unavailable", "Tutor dependencies are not configured", 503
        )
    return service


def _citation(item: Any) -> CitationResponse:
    if isinstance(item, dict):
        return CitationResponse(**item)
    return CitationResponse(
        fragment_id=item.fragment_id,
        unit_number=getattr(item, "unit_number", None),
        pdf_page=item.pdf_page,
        printed_page=item.printed_page,
        image_url=getattr(item, "image_url", None),
    )


def _summary(item: ConversationRecord) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        id=item.id,
        title=item.title,
        language=Language(item.language),
        addressing_preference=item.addressing_preference,
        expires_at=item.expires_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _exchange(item: ExchangeRecord) -> ExchangeResponse:
    return ExchangeResponse(
        id=item.id,
        sequence_number=item.sequence_number,
        question=item.question,
        answer=item.answer,
        language=Language(item.language),
        upload_id=item.upload_id,
        citations=tuple(_citation(citation) for citation in item.citations),
        created_at=item.created_at,
    )


def _answer(item: TutorAnswer) -> TutorResponse:
    return TutorResponse(
        answer=item.answer,
        language=item.language,
        scope_status=item.scope_status,
        conversation_id=item.conversation_id,
        citations=tuple(_citation(citation) for citation in item.citations),
    )


@router.post(
    "/conversations",
    response_model=ConversationSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: CreateConversationRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> ConversationSummaryResponse:
    return _summary(
        service.create_conversation(
            user.id,
            payload.language,
            payload.title,
            payload.addressing_preference,
        )
    )


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> ConversationListResponse:
    return ConversationListResponse(
        items=tuple(_summary(item) for item in service.list_conversations(user.id))
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_conversation(
    conversation_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> ConversationDetailResponse:
    conversation, exchanges = service.get_conversation(user.id, conversation_id)
    summary = _summary(conversation)
    return ConversationDetailResponse(
        **summary.model_dump(),
        exchanges=tuple(_exchange(item) for item in exchanges),
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> Response:
    if not service.delete_conversation(user.id, conversation_id):
        raise ApplicationError(
            "conversation_not_found", "Conversation was not found", 404
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_id}/ask",
    response_model=TutorResponse,
)
def ask_in_conversation(
    conversation_id: UUID,
    payload: AskTutorRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> TutorResponse:
    return _answer(
        service.ask(
            payload.question,
            payload.language,
            user_id=user.id,
            upload_id=payload.upload_id,
            conversation_id=conversation_id,
            addressing_preference=payload.addressing_preference,
        )
    )


@router.post("/ask", response_model=TutorResponse)
def ask_tutor(
    payload: AskTutorRequest,
    _user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> TutorResponse:
    answer = service.ask(
        payload.question,
        payload.language,
        user_id=_user.id,
        upload_id=payload.upload_id,
        addressing_preference=payload.addressing_preference,
    )
    return _answer(answer)
