from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from english7.api.errors import ApplicationError


@dataclass(frozen=True)
class GradingQuestion:
    id: UUID
    expected: str | None


@dataclass(frozen=True)
class GradedAnswer:
    question_id: UUID
    answer: str
    correct: bool


@dataclass(frozen=True)
class AttemptResult:
    quiz_id: UUID
    submitted_at: datetime
    correct: int
    total: int


class ProgressRepository(Protocol):
    def submit(self, user_id: UUID, quiz_id: UUID,
               grade: Callable[[list[GradingQuestion]], list[GradedAnswer]]) -> AttemptResult: ...

    def history(self, user_id: UUID) -> list[AttemptResult]: ...


class ProgressService:
    def __init__(self, repository: ProgressRepository):
        self._repository = repository

    def submit(self, user_id: UUID, quiz_id: UUID, answers: dict[str, str]) -> AttemptResult:
        def _is_match(ans: str, exp: str | None) -> bool:
            if not exp or not ans:
                return False
            a = ans.strip().casefold()
            e = exp.strip().casefold()
            if a == e:
                return True
            if len(a) == 1 and (e.startswith(f"{a}.") or e.startswith(f"{a})") or e.startswith(f"{a} ")):
                return True
            if len(e) == 1 and (a.startswith(f"{e}.") or a.startswith(f"{e})") or a.startswith(f"{e} ")):
                return True
            return False

        def grade(questions: list[GradingQuestion]) -> list[GradedAnswer]:
            if not questions:
                raise ApplicationError('quiz_empty', 'Quiz has no questions', 409)
            if set(answers) - {str(q.id) for q in questions}:
                raise ApplicationError('invalid_answers', 'Answer does not belong to this quiz', 422)
            return [GradedAnswer(
                q.id, answers.get(str(q.id), ''),
                _is_match(answers.get(str(q.id), ''), q.expected),
            ) for q in questions]

        return self._repository.submit(user_id, quiz_id, grade)

    def progress(self, user_id: UUID) -> dict:
        history = self._repository.history(user_id)
        return {
            'completed_quizzes': len(history),
            'correct': sum(item.correct for item in history),
            'total': sum(item.total for item in history),
            'history': history,
        }
