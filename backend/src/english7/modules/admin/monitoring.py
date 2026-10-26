from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from english7.api.errors import ApplicationError
from english7.db.models import TutorChat, TutorConversation, User


class AdminMonitoringService:
    def __init__(self, session_factory) -> None:
        self._sessions = session_factory

    def list_conversations(self) -> list[dict]:
        with self._sessions() as session:
            records = session.scalars(
                select(TutorConversation)
                .options(
                    selectinload(TutorConversation.user),
                    selectinload(TutorConversation.exchanges),
                )
                .order_by(TutorConversation.updated_at.desc())
                .limit(200)
            ).all()
            return [
                {
                    "id": item.id,
                    "student_id": item.user_id,
                    "student_email": item.user.email,
                    "student_name": item.user.full_name,
                    "title": item.title,
                    "language": item.language,
                    "exchange_count": len(item.exchanges),
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                }
                for item in records
            ]

    def list_chat_students(self) -> list[dict]:
        with self._sessions() as session:
            rows = session.execute(
                select(
                    TutorChat.user_id,
                    User.email,
                    User.full_name,
                    func.count(TutorChat.id).label("exchange_count"),
                    func.max(TutorChat.created_at).label("last_activity_at"),
                )
                .join(User, User.id == TutorChat.user_id)
                .group_by(TutorChat.user_id, User.email, User.full_name)
                .order_by(func.max(TutorChat.created_at).desc())
            ).all()
            return [
                {
                    "student_id": row.user_id,
                    "student_email": row.email,
                    "student_name": row.full_name,
                    "exchange_count": row.exchange_count,
                    "last_activity_at": row.last_activity_at,
                }
                for row in rows
            ]

    def student_chat_history(self, student_id: UUID) -> dict:
        with self._sessions() as session:
            student = session.get(User, student_id)
            if student is None:
                raise ApplicationError(
                    "student_not_found", "Student was not found", 404
                )
            exchanges = session.scalars(
                select(TutorChat)
                .where(TutorChat.user_id == student_id)
                .order_by(
                    TutorChat.created_at.asc(),
                    TutorChat.conversation_id.asc(),
                    TutorChat.sequence_number.asc(),
                )
            ).all()
            return {
                "student_id": student.id,
                "student_email": student.email,
                "student_name": student.full_name,
                "exchange_count": len(exchanges),
                "last_activity_at": (
                    exchanges[-1].created_at if exchanges else None
                ),
                "exchanges": [
                    {
                        "id": exchange.id,
                        "conversation_id": exchange.conversation_id,
                        "sequence_number": exchange.sequence_number,
                        "question": exchange.question,
                        "answer": exchange.answer,
                        "language": exchange.language,
                        "citations": exchange.citations or [],
                        "created_at": exchange.created_at,
                    }
                    for exchange in exchanges
                ],
            }

    def conversation(self, conversation_id: UUID) -> dict:
        with self._sessions() as session:
            item = session.scalar(
                select(TutorConversation)
                .where(TutorConversation.id == conversation_id)
                .options(
                    selectinload(TutorConversation.user),
                    selectinload(TutorConversation.exchanges),
                )
            )
            if item is None:
                raise ApplicationError(
                    "conversation_not_found", "Conversation was not found", 404
                )
            return {
                "id": item.id,
                "student_id": item.user_id,
                "student_email": item.user.email,
                "student_name": item.user.full_name,
                "title": item.title,
                "language": item.language,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "exchanges": [
                    {
                        "id": exchange.id,
                        "sequence_number": exchange.sequence_number,
                        "question": exchange.question,
                        "answer": exchange.answer,
                        "language": exchange.language,
                        "citations": exchange.citations or [],
                        "created_at": exchange.created_at,
                    }
                    for exchange in item.exchanges
                ],
            }
