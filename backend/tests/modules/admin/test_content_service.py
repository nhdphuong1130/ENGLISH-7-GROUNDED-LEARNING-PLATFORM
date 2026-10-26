from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.api.errors import ApplicationError
from english7.db.base import Base
from english7.db.models import Activity, Role, Section, SourceDocument, Textbook, User
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.admin.content_service import AdminContentService


def _service():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        role = Role(name="admin")
        textbook = Textbook(title="English 7", edition="2026", is_active=True)
        session.add_all([role, textbook])
        session.flush()
        admin = User(
            email="admin@example.com",
            password_hash="hash",
            role_id=role.id,
        )
        source = SourceDocument(
            textbook_id=textbook.id,
            original_filename="book.pdf",
            object_key="book.pdf",
            file_hash="hash",
            page_count=200,
            ingestion_version="v1",
        )
        session.add_all([admin, source])
        session.commit()
        values = admin.id, textbook.id, source.id
    return factory, AdminContentService(factory, AdminAuditService(factory)), values


def test_unit_changes_create_versions_and_reject_stale_update() -> None:
    _factory, service, (admin_id, textbook_id, _source_id) = _service()
    created = service.create_unit(
        textbook_id=textbook_id,
        number=1,
        title="My Hobbies",
        actor_id=admin_id,
    )

    assert created["version"] == 1
    assert created["status"] == "draft"
    updated = service.update_unit(
        created["id"],
        {"title": "Hobbies"},
        expected_version=1,
        actor_id=admin_id,
    )
    assert updated["version"] == 2

    with pytest.raises(ApplicationError) as error:
        service.update_unit(
            created["id"],
            {"title": "Stale"},
            expected_version=1,
            actor_id=admin_id,
        )
    assert error.value.code == "content_version_conflict"


def test_fragment_publish_requires_verified_textbook_page() -> None:
    factory, service, (admin_id, textbook_id, source_id) = _service()
    unit = service.create_unit(
        textbook_id=textbook_id,
        number=1,
        title="My Hobbies",
        actor_id=admin_id,
    )
    with factory() as session:
        section = Section(unit_id=unit["id"], title="Getting Started", section_type="lesson", position=1)
        session.add(section)
        session.flush()
        activity = Activity(section_id=section.id, number="1", activity_type="reading", instruction="Read")
        session.add(activity)
        session.commit()
        activity_id = activity.id
    fragment = service.create_fragment(
        source_document_id=source_id,
        activity_id=activity_id,
        pdf_page=10,
        printed_page=None,
        normalized_text="Page content",
        actor_id=admin_id,
    )

    with pytest.raises(ApplicationError) as error:
        service.publish_fragment(
            fragment["id"],
            expected_version=1,
            actor_id=admin_id,
        )
    assert error.value.code == "grounding_required"

    updated = service.update_fragment(
        fragment["id"],
        {"printed_page": 12, "review_status": "verified"},
        expected_version=1,
        actor_id=admin_id,
    )
    published = service.publish_fragment(
        fragment["id"],
        expected_version=updated["version"],
        actor_id=admin_id,
    )
    assert published["status"] == "published"
    assert published["is_published"] is True


def test_restore_creates_a_new_draft_version() -> None:
    _factory, service, (admin_id, textbook_id, _source_id) = _service()
    unit = service.create_unit(
        textbook_id=textbook_id,
        number=2,
        title="Healthy Living",
        actor_id=admin_id,
    )
    service.update_unit(
        unit["id"],
        {"title": "Changed"},
        expected_version=1,
        actor_id=admin_id,
    )

    restored = service.restore("unit", unit["id"], version=1, actor_id=admin_id)

    assert restored["title"] == "Healthy Living"
    assert restored["version"] == 3
    assert restored["status"] == "draft"


def test_section_activity_crud_and_preview_are_versioned() -> None:
    _factory, service, (admin_id, textbook_id, _source_id) = _service()
    unit = service.create_unit(
        textbook_id=textbook_id,
        number=3,
        title="Community Service",
        actor_id=admin_id,
    )
    section = service.create_section(
        unit["id"],
        title="A Closer Look",
        section_type="lesson",
        position=1,
        actor_id=admin_id,
    )
    section = service.update_section(
        section["id"],
        {"title": "A Closer Look 1"},
        expected_version=1,
        actor_id=admin_id,
    )
    activity = service.create_activity(
        section["id"],
        number="1",
        activity_type="vocabulary",
        instruction="Match the words",
        actor_id=admin_id,
    )
    activity = service.update_activity(
        activity["id"],
        {"instruction": "Match words and pictures"},
        expected_version=1,
        actor_id=admin_id,
    )

    assert service.list_units()[0]["child_count"] == 1
    assert service.list_sections(unit["id"])[0]["child_count"] == 1
    assert service.list_activities(section["id"])[0]["child_count"] == 0

    assert section["version"] == 2
    assert activity["version"] == 2
    assert service.preview("activity", activity["id"])["instruction"] == "Match words and pictures"

    service.delete_activity(activity["id"], actor_id=admin_id)
    service.delete_section(section["id"], actor_id=admin_id)


def test_fragment_archive_and_delete() -> None:
    _factory, service, (admin_id, textbook_id, source_id) = _service()
    unit = service.create_unit(textbook_id=textbook_id, number=4, title="Music", actor_id=admin_id)
    section = service.create_section(unit["id"], title="Skills", section_type="lesson", position=1, actor_id=admin_id)
    activity = service.create_activity(section["id"], number="2", activity_type="reading", instruction=None, actor_id=admin_id)
    fragment = service.create_fragment(
        source_document_id=source_id,
        activity_id=activity["id"],
        pdf_page=30,
        printed_page=28,
        normalized_text="Music makes life better.",
        actor_id=admin_id,
    )

    archived = service.archive_fragment(fragment["id"], actor_id=admin_id)
    assert archived["status"] == "archived"
    assert archived["version"] == 2
    service.delete_fragment(fragment["id"], actor_id=admin_id)
