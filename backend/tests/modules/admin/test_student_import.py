from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.core.security import PasswordHasher
from english7.db.base import Base
from english7.db.models import Role, User
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.admin.import_service import StudentImportService
from english7.modules.admin.exports import student_accounts_csv


def _service():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all([Role(name="student"), Role(name="admin")])
        session.commit()
    return factory, StudentImportService(
        factory,
        PasswordHasher(),
        AdminAuditService(factory),
    )


def test_student_csv_dry_run_reports_rows_without_writing() -> None:
    factory, service = _service()
    report = service.import_students(
        b"email,password,full_name,class_name\nnew@example.com,SecurePass123!,New Student,7A\n",
        filename="students.csv",
        dry_run=True,
        actor_id=uuid4(),
    )

    assert report.valid_rows == 1
    assert report.errors == []
    assert report.applied is False
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0


def test_student_csv_apply_is_atomic_when_any_row_is_invalid() -> None:
    factory, service = _service()
    report = service.import_students(
        b"email,password,full_name\nvalid@example.com,SecurePass123!,Valid\ninvalid@example.com,short,Invalid\n",
        filename="students.csv",
        dry_run=False,
        actor_id=uuid4(),
    )

    assert report.valid_rows == 1
    assert report.applied is False
    assert report.errors[0]["row"] == 3
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0


def test_student_csv_apply_creates_all_valid_students() -> None:
    factory, service = _service()
    report = service.import_students(
        b"email,password,full_name\na@example.com,SecurePass123!,A\nb@example.com,SecurePass456!,B\n",
        filename="students.csv",
        dry_run=False,
        actor_id=uuid4(),
    )

    assert report.applied is True
    assert report.created == 2
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 2


def test_student_account_export_excludes_password_data() -> None:
    content = student_accounts_csv(
        [
            {
                "email": "student@example.com",
                "full_name": "Student",
                "school_name": "School",
                "class_name": "7A",
                "status": "active",
                "password_hash": "must-not-leak",
            }
        ]
    ).decode("utf-8-sig")

    assert "student@example.com" in content
    assert "active" in content
    assert "must-not-leak" not in content
