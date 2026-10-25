from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


@dataclass(slots=True)
class AIProviderError(Exception):
    code: str
    message: str = "The AI provider request failed"

    def __str__(self) -> str:
        return self.message


class Language(StrEnum):
    VIETNAMESE = "vi"
    ENGLISH = "en"


class ScopeStatus(StrEnum):
    GROUNDED = "grounded"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    learner: str
    tutor: str


@dataclass(frozen=True, slots=True)
class Evidence:
    fragment_id: UUID
    text: str
    pdf_page: int
    printed_page: int | None


@dataclass(frozen=True, slots=True)
class AIRequest:
    question: str
    language: Language
    evidence: tuple[Evidence, ...]
    history: tuple[ConversationTurn, ...] = ()
    addressing_preference: str | None = None


@dataclass(frozen=True, slots=True)
class AIResponse:
    answer: str
    language: Language
    citations: tuple[UUID, ...]
    scope_status: ScopeStatus = ScopeStatus.GROUNDED


class AIProvider(Protocol):
    def generate(self, request: AIRequest) -> AIResponse: ...
