from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.api.errors import ApplicationError
from english7.db.base import Base
from english7.db.models import Activity, Role, Section, SourceDocument, SourceFragment, Textbook, Unit, User
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.admin.practice_service import AdminPracticeService
from english7.main import app
from english7.modules.admin.practice_router import get_admin_practice_service
from english7.modules.auth.domain import AuthUser
from english7.modules.auth.router import get_current_user


class PronunciationStub:
    def pronounce(self, text: str) -> str:
        return f"/{text}/"


def _service():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        role = Role(name="admin")
        textbook = Textbook(title="English 7", is_active=True)
        session.add_all([role, textbook])
        session.flush()
        admin = User(email="admin@example.com", password_hash="hash", role_id=role.id)
        unit = Unit(textbook_id=textbook.id, number=1, title="Hobbies", is_published=True)
        source = SourceDocument(textbook_id=textbook.id, original_filename="book.pdf", object_key="book.pdf", file_hash="hash", page_count=200, ingestion_version="v1")
        session.add_all([admin, unit, source])
        session.flush()
        section = Section(unit_id=unit.id, title="Vocabulary", section_type="lesson", position=1)
        session.add(section)
        session.flush()
        activity = Activity(section_id=section.id, number="1", activity_type="vocabulary")
        session.add(activity)
        session.flush()
        fragment = SourceFragment(source_document_id=source.id, activity_id=activity.id, pdf_page=10, printed_page=8, region_type="text", x=0, y=0, width=1, height=1, normalized_text="collecting dolls", review_status="verified", is_published=True)
        session.add(fragment)
        session.commit()
        ids = admin.id, unit.id, fragment.id
    return factory, AdminPracticeService(factory, AdminAuditService(factory), PronunciationStub()), ids


def test_textbook_card_generates_ipa_and_requires_grounding_to_publish() -> None:
    _factory, service, (admin_id, unit_id, fragment_id) = _service()
    deck = service.create_deck(name="Unit 1", unit_id=unit_id, actor_id=admin_id)
    card = service.create_card(deck["id"], word="hobby", meaning="sở thích", source_fragment_id=fragment_id, actor_id=admin_id)

    assert card["ipa"] == "/hobby/"
    assert card["page"] == 8
    published = service.publish_card(card["id"], expected_version=1, actor_id=admin_id)
    assert published["is_published"] is True


def test_blueprint_delete_is_refused_after_quiz_usage() -> None:
    factory, service, (admin_id, _unit_id, _fragment_id) = _service()
    blueprint = service.create_blueprint(name="Unit test", duration_minutes=15, difficulty="easy", policy={}, actor_id=admin_id)
    from english7.db.models import Quiz
    with factory() as session:
        session.add(Quiz(blueprint_id=blueprint["id"], created_for_user_id=admin_id, is_locked=False))
        session.commit()

    with pytest.raises(ApplicationError) as error:
        service.delete_blueprint(blueprint["id"], actor_id=admin_id)
    assert error.value.code == "practice_content_in_use"


def test_practice_management_is_admin_only(client) -> None:
    class FakeService:
        def list_blueprints(self):
            return []

    app.dependency_overrides[get_admin_practice_service] = FakeService
    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=uuid4(), email="student@example.com", password_hash="hash", role="student"
    )
    try:
        response = client.get("/api/v1/admin/practice/quiz-blueprints")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
