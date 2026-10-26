from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.db.base import Base
from english7.modules.admin.audit_service import AdminAuditService


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_audit_service_redacts_secrets_recursively() -> None:
    service = AdminAuditService(_session_factory())
    event = service.record(
        actor_id=None,
        action="student.password_reset",
        entity_type="user",
        entity_id=uuid4(),
        before={"email": "a@example.com"},
        after={
            "password": "secret",
            "nested": {"access_token": "token", "name": "Student"},
        },
        request_id="req-1",
        ip_address="127.0.0.1",
        platform="web",
    )

    assert event.after_data == {
        "password": "[REDACTED]",
        "nested": {"access_token": "[REDACTED]", "name": "Student"},
    }
    assert event.succeeded is True


def test_audit_service_lists_newest_events_first() -> None:
    service = AdminAuditService(_session_factory())
    first = service.record(
        actor_id=None,
        action="student.created",
        entity_type="user",
        entity_id=uuid4(),
    )
    second = service.record(
        actor_id=None,
        action="student.locked",
        entity_type="user",
        entity_id=uuid4(),
    )

    events = service.list_events(offset=0, limit=20)

    assert [event.id for event in events] == [second.id, first.id]
