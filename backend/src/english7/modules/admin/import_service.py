from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from uuid import UUID, uuid4
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from english7.api.errors import ApplicationError
from english7.core.security import PasswordHasher
from english7.db.models import Role, User
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.auth.service import AuthService


MAX_IMPORT_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class StudentImportReport:
    valid_rows: int
    created: int
    applied: bool
    errors: list[dict[str, object]]


class StudentImportService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        password_hasher: PasswordHasher,
        audit_service: AdminAuditService,
    ) -> None:
        self._session_factory = session_factory
        self._password_hasher = password_hasher
        self._audit = audit_service

    def import_students(
        self,
        data: bytes,
        *,
        filename: str,
        dry_run: bool,
        actor_id: UUID,
        request_id: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
    ) -> StudentImportReport:
        if len(data) > MAX_IMPORT_BYTES:
            raise ApplicationError("import_too_large", "Import file exceeds 5 MiB", 413)
        rows = self._read_rows(data, filename)
        errors: list[dict[str, object]] = []
        valid: list[dict[str, str | None]] = []
        seen: set[str] = set()
        with self._session_factory() as session:
            existing = set(session.scalars(select(User.email)))
        for number, raw in enumerate(rows, start=2):
            normalized = {
                str(key).strip().casefold(): (value.strip() if value else "")
                for key, value in raw.items()
                if key is not None
            }
            login_value = normalized.get("email") or normalized.get("phone") or ""
            password = normalized.get("password", "")
            try:
                login = self._normalize_login(login_value)
            except ApplicationError as error:
                errors.append({"row": number, "field": "email", "message": error.message})
                continue
            row_errors: list[tuple[str, str]] = []
            if len(password) < 8:
                row_errors.append(("password", "Password must contain at least 8 characters"))
            if login in seen or login in existing:
                row_errors.append(("email", "Email or phone is duplicated"))
            if row_errors:
                errors.extend(
                    {"row": number, "field": field, "message": message}
                    for field, message in row_errors
                )
                continue
            seen.add(login)
            valid.append(
                {
                    "email": login,
                    "password": password,
                    "full_name": normalized.get("full_name") or None,
                    "school_name": normalized.get("school_name") or None,
                    "class_name": normalized.get("class_name") or None,
                }
            )
        if dry_run or errors:
            return StudentImportReport(len(valid), 0, False, errors)

        created_ids: list[UUID] = []
        with self._session_factory() as session:
            role_id = session.scalar(select(Role.id).where(Role.name == "student"))
            if role_id is None:
                raise RuntimeError("Student role is not seeded")
            for row in valid:
                user = User(
                    email=str(row["email"]),
                    password_hash=self._password_hasher.hash(str(row["password"])),
                    role_id=role_id,
                    full_name=row["full_name"],
                    school_name=row["school_name"],
                    class_name=row["class_name"],
                )
                session.add(user)
                session.flush()
                created_ids.append(user.id)
            session.commit()
        self._audit.record(
            actor_id=actor_id,
            action="students.imported",
            entity_type="student_import",
            entity_id=uuid4(),
            after={"created": len(created_ids), "student_ids": [str(value) for value in created_ids]},
            request_id=request_id,
            ip_address=ip_address,
            platform=platform,
        )
        return StudentImportReport(len(valid), len(created_ids), True, [])

    @staticmethod
    def _normalize_login(value: str) -> str:
        clean = value.strip().lower()
        if "@" in clean and len(clean) >= 3:
            return clean
        digits = "".join(character for character in clean if character.isdigit())
        if len(digits) < 9:
            raise ApplicationError("student_login_invalid", "Email or phone number is invalid", 422)
        return AuthService.phone_to_email(digits)

    @staticmethod
    def _read_rows(data: bytes, filename: str) -> list[dict[str, str]]:
        suffix = Path(filename).suffix.casefold()
        if suffix == ".csv":
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError as error:
                raise ApplicationError("import_encoding_invalid", "CSV must use UTF-8", 422) from error
            return list(csv.DictReader(StringIO(text)))
        if suffix == ".xlsx":
            return StudentImportService._read_xlsx(data)
        raise ApplicationError("import_format_invalid", "Only CSV and XLSX files are supported", 422)

    @staticmethod
    def _read_xlsx(data: bytes) -> list[dict[str, str]]:
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        try:
            with ZipFile(BytesIO(data)) as archive:
                shared: list[str] = []
                if "xl/sharedStrings.xml" in archive.namelist():
                    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                    shared = ["".join(node.itertext()) for node in root.findall("x:si", namespace)]
                sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        except (BadZipFile, KeyError, ElementTree.ParseError) as error:
            raise ApplicationError("import_xlsx_invalid", "XLSX file is invalid", 422) from error
        table: list[list[str]] = []
        for row in sheet.findall(".//x:row", namespace):
            values: list[str] = []
            for cell in row.findall("x:c", namespace):
                cell_type = cell.get("t")
                if cell_type == "inlineStr":
                    value = "".join(cell.itertext())
                else:
                    node = cell.find("x:v", namespace)
                    value = node.text if node is not None and node.text else ""
                    if cell_type == "s" and value:
                        value = shared[int(value)]
                values.append(value)
            table.append(values)
        if not table:
            return []
        headers = table[0]
        return [dict(zip(headers, row, strict=False)) for row in table[1:]]
