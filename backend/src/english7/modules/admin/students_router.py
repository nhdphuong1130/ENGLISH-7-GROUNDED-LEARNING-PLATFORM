from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from english7.core.security import PasswordHasher
from english7.db.session import get_session_factory
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.admin.dependencies import AdminUser
from english7.modules.admin.student_service import AdminStudent, AdminStudentService
from english7.modules.admin.import_service import StudentImportService
from english7.modules.auth.domain import ProfileGender


router = APIRouter(prefix="/students", tags=["admin-students"])


def get_admin_student_service() -> AdminStudentService:
    factory = get_session_factory()
    return AdminStudentService(factory, PasswordHasher(), AdminAuditService(factory))


StudentService = Annotated[AdminStudentService, Depends(get_admin_student_service)]


def get_admin_import_service() -> StudentImportService:
    factory = get_session_factory()
    return StudentImportService(factory, PasswordHasher(), AdminAuditService(factory))


ImportService = Annotated[StudentImportService, Depends(get_admin_import_service)]


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    date_of_birth: date | None
    gender: str | None
    school_name: str | None
    class_name: str | None
    is_active: bool
    archived_at: datetime | None
    status: str


class StudentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    gender: ProfileGender | None = None
    school_name: str | None = Field(default=None, max_length=255)
    class_name: str | None = Field(default=None, max_length=100)


class StudentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, min_length=3, max_length=320)
    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    gender: ProfileGender | None = None
    school_name: str | None = Field(default=None, max_length=255)
    class_name: str | None = Field(default=None, max_length=100)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=8, max_length=128)


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: str = Field(min_length=1, max_length=320)


def _context(request: Request) -> dict[str, str | None]:
    return {
        "request_id": getattr(request.state, "trace_id", None),
        "ip_address": request.client.host if request.client else None,
        "platform": request.headers.get("x-client-platform"),
    }


def _response(student: AdminStudent) -> StudentResponse:
    return StudentResponse.model_validate(student)


@router.get("")
def list_students(
    _admin: AdminUser,
    service: StudentService,
    q: str | None = Query(default=None, max_length=255),
    status: Literal["all", "active", "locked", "archived"] = "all",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    items = service.list_students(query=q, status=status, offset=offset, limit=limit)
    return {"items": [_response(item) for item in items], "count": len(items), "offset": offset, "limit": limit}


@router.post("/import")
async def import_students(
    request: Request,
    admin: AdminUser,
    service: ImportService,
    file: Annotated[UploadFile, File()],
    dry_run: bool = True,
) -> dict[str, Any]:
    try:
        data = await file.read(5 * 1024 * 1024 + 1)
        report = service.import_students(
            data,
            filename=file.filename or "students.csv",
            dry_run=dry_run,
            actor_id=admin.id,
            **_context(request),
        )
        return {
            "valid_rows": report.valid_rows,
            "created": report.created,
            "applied": report.applied,
            "errors": report.errors,
        }
    finally:
        await file.close()


@router.get("/accounts/export")
def export_student_accounts(
    _admin: AdminUser,
    service: StudentService,
    format: Literal["csv", "xlsx"] = "xlsx",
) -> Response:
    from english7.modules.admin.exports import (
        student_accounts_csv,
        student_accounts_xlsx,
    )

    students = service.list_students(
        query=None,
        status="all",
        offset=0,
        limit=10_000,
    )
    rows = [
        {
            "email": item.email,
            "full_name": item.full_name,
            "school_name": item.school_name,
            "class_name": item.class_name,
            "status": item.status,
        }
        for item in students
    ]
    if format == "csv":
        content = student_accounts_csv(rows)
        media_type = "text/csv; charset=utf-8"
    else:
        content = student_accounts_xlsx(rows)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="student-accounts.{format}"'
        },
    )


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: UUID, _admin: AdminUser, service: StudentService) -> StudentResponse:
    return _response(service.get_student(student_id))


@router.post("", response_model=StudentResponse, status_code=201)
def create_student(payload: StudentCreateRequest, request: Request, admin: AdminUser, service: StudentService) -> StudentResponse:
    return _response(
        service.create_student(
            **payload.model_dump(mode="python"),
            actor_id=admin.id,
            **_context(request),
        )
    )


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(student_id: UUID, payload: StudentUpdateRequest, request: Request, admin: AdminUser, service: StudentService) -> StudentResponse:
    changes = payload.model_dump(exclude_unset=True, mode="python")
    return _response(service.update_student(student_id, changes, actor_id=admin.id, **_context(request)))


@router.post("/{student_id}/reset-password", status_code=204)
def reset_student_password(student_id: UUID, payload: PasswordResetRequest, request: Request, admin: AdminUser, service: StudentService) -> Response:
    service.reset_password(student_id, payload.new_password, actor_id=admin.id, **_context(request))
    return Response(status_code=204)


@router.post("/{student_id}/lock", response_model=StudentResponse)
def lock_student(student_id: UUID, request: Request, admin: AdminUser, service: StudentService) -> StudentResponse:
    return _response(service.set_locked(student_id, True, actor_id=admin.id, **_context(request)))


@router.post("/{student_id}/unlock", response_model=StudentResponse)
def unlock_student(student_id: UUID, request: Request, admin: AdminUser, service: StudentService) -> StudentResponse:
    return _response(service.set_locked(student_id, False, actor_id=admin.id, **_context(request)))


@router.post("/{student_id}/archive", response_model=StudentResponse)
def archive_student(student_id: UUID, _payload: ConfirmationRequest, request: Request, admin: AdminUser, service: StudentService) -> StudentResponse:
    return _response(service.archive(student_id, actor_id=admin.id, **_context(request)))


@router.post("/{student_id}/restore", response_model=StudentResponse)
def restore_student(student_id: UUID, request: Request, admin: AdminUser, service: StudentService) -> StudentResponse:
    return _response(service.restore(student_id, actor_id=admin.id, **_context(request)))


@router.delete("/{student_id}", status_code=204)
def delete_student(student_id: UUID, confirmation: str, request: Request, admin: AdminUser, service: StudentService) -> Response:
    service.delete_student(student_id, confirmation=confirmation, actor_id=admin.id, **_context(request))
    return Response(status_code=204)
