from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from english7.db.models import AuditEvent


_SECRET_MARKERS = (
    "password",
    "token",
    "otp",
    "api_key",
    "secret",
)


def _redact(value: Any, *, key: str | None = None) -> Any:
    if key is not None and any(marker in key.casefold() for marker in _SECRET_MARKERS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): _redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact(item) for item in value]
    return value


class AdminAuditService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
        succeeded: bool = True,
        event_data: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            event_data=_redact(event_data or {}),
            request_id=request_id,
            ip_address=ip_address,
            platform=platform,
            before_data=_redact(before) if before is not None else None,
            after_data=_redact(after) if after is not None else None,
            succeeded=succeeded,
        )
        with self._session_factory() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
            session.expunge(event)
        return event

    def list_events(self, *, offset: int, limit: int) -> list[AuditEvent]:
        with self._session_factory() as session:
            events = list(
                session.scalars(
                    select(AuditEvent)
                    .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
            for event in events:
                session.expunge(event)
            return events
