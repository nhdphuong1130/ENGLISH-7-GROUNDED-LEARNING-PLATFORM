from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from english7.db.models import ContentRevision, Role, TestAttempt, User


class AdminDashboardService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def summary(self) -> dict[str, Any]:
        with self._session_factory() as session:
            student_filter = User.role_id == Role.id
            base = select(func.count()).select_from(User).join(Role).where(
                student_filter,
                Role.name == "student",
            )
            total = session.scalar(base) or 0
            active = session.scalar(
                base.where(User.is_active.is_(True), User.archived_at.is_(None))
            ) or 0
            locked = session.scalar(
                base.where(User.is_active.is_(False), User.archived_at.is_(None))
            ) or 0
            archived = session.scalar(base.where(User.archived_at.is_not(None))) or 0
            submitted = session.scalar(
                select(func.count()).select_from(TestAttempt).where(
                    TestAttempt.status == "submitted"
                )
            ) or 0
            drafts = session.scalar(
                select(func.count()).select_from(ContentRevision).where(
                    ContentRevision.status == "draft"
                )
            ) or 0
        return {
            "total_students": total,
            "active_students": active,
            "locked_students": locked,
            "archived_students": archived,
            "submitted_tests": submitted,
            "draft_content": drafts,
        }
