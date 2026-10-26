from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.api.errors import ApplicationError
from english7.core.security import PasswordHasher
from english7.db.base import Base
from english7.db.models import AuditEvent, MasteryRecord, Role, User
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.admin.student_service import AdminStudentService


def _services():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        student_role = Role(name="student")
        admin_role = Role(name="admin")
        session.add_all([student_role, admin_role])
        session.flush()
        admin = User(
            id=uuid4(),
            email="admin@example.com",
            password_hash="hash",
            role_id=admin_role.id,
        )
        student = User(
            id=uuid4(),
            email="student@example.com",
            password_hash="hash",
            role_id=student_role.id,
            full_name="Old Name",
        )
        session.add_all([admin, student])
        session.commit()
    service = AdminStudentService(
        factory,
        PasswordHasher(),
        AdminAuditService(factory),
    )
    return factory, service, admin.id, student.id


def test_admin_manages_complete_student_lifecycle() -> None:
    factory, service, admin_id, student_id = _services()

    listed = service.list_students(query="Old", status="active", offset=0, limit=20)
    assert [item.id for item in listed] == [student_id]

    updated = service.update_student(
        student_id,
        {"full_name": "New Name", "school_name": "School A", "class_name": "7A"},
        actor_id=admin_id,
    )
    assert updated.full_name == "New Name"

    locked = service.set_locked(student_id, True, actor_id=admin_id)
    assert locked.status == "locked"
    restored = service.set_locked(student_id, False, actor_id=admin_id)
    assert restored.status == "active"

    archived = service.archive(student_id, actor_id=admin_id)
    assert archived.status == "archived"
    active = service.restore(student_id, actor_id=admin_id)
    assert active.status == "active"

    service.reset_password(student_id, "NewSecurePass123!", actor_id=admin_id)
    with factory() as session:
        row = session.get(User, student_id)
        assert row is not None
        assert PasswordHasher().verify("NewSecurePass123!", row.password_hash)
        actions = list(session.scalars(select(AuditEvent.action)))
    assert "student.updated" in actions
    assert "student.password_reset" in actions


def test_admin_creates_and_permanently_deletes_empty_student() -> None:
    _factory, service, admin_id, _student_id = _services()
    created = service.create_student(
        email="new@example.com",
        password="SecurePass123!",
        full_name="New Student",
        school_name=None,
        class_name="7B",
        actor_id=admin_id,
    )

    service.delete_student(
        created.id,
        confirmation="new@example.com",
        actor_id=admin_id,
    )

    with pytest.raises(ApplicationError) as error:
        service.get_student(created.id)
    assert error.value.code == "student_not_found"


def test_admin_delete_requires_exact_confirmation() -> None:
    _factory, service, admin_id, student_id = _services()

    with pytest.raises(ApplicationError) as error:
        service.delete_student(student_id, confirmation="wrong", actor_id=admin_id)

    assert error.value.code == "confirmation_mismatch"


def test_admin_permanent_delete_removes_related_learning_data() -> None:
    factory, service, admin_id, student_id = _services()
    with factory() as session:
        session.add(
            MasteryRecord(
                user_id=student_id,
                concept_key="vocab-u1-hobby",
                mastery_score=0.5,
                attempt_count=2,
            )
        )
        session.commit()

    service.delete_student(
        student_id,
        confirmation="student@example.com",
        actor_id=admin_id,
    )

    with factory() as session:
        assert session.get(User, student_id) is None
        assert session.scalar(
            select(MasteryRecord).where(MasteryRecord.user_id == student_id)
        ) is None
