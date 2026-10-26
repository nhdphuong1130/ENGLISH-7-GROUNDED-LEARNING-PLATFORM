from uuid import uuid4

from english7.db.models import AuditEvent, ContentRevision, User


def test_admin_management_models_capture_lifecycle_and_revision() -> None:
    actor_id = uuid4()
    entity_id = uuid4()
    user = User(
        email="student@example.com",
        password_hash="hash",
        role_id=uuid4(),
    )
    revision = ContentRevision(
        entity_type="unit",
        entity_id=entity_id,
        version=1,
        status="draft",
        snapshot={"number": 1, "title": "My Hobbies"},
        actor_id=actor_id,
    )
    audit = AuditEvent(
        actor_id=actor_id,
        action="unit.created",
        entity_type="unit",
        entity_id=entity_id,
        event_data={},
        request_id="request-1",
        ip_address="127.0.0.1",
        platform="web",
        before_data=None,
        after_data={"title": "My Hobbies"},
        succeeded=True,
    )

    assert user.archived_at is None
    assert revision.status == "draft"
    assert revision.snapshot["number"] == 1
    assert audit.request_id == "request-1"
    assert audit.succeeded is True
