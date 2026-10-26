from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from english7.db.session import get_session_factory
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.admin.content_service import AdminContentService
from english7.modules.admin.dependencies import AdminUser


router = APIRouter(prefix="/content", tags=["admin-content"])


def get_admin_content_service() -> AdminContentService:
    factory = get_session_factory()
    return AdminContentService(factory, AdminAuditService(factory))


ContentService = Annotated[AdminContentService, Depends(get_admin_content_service)]


class UnitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    textbook_id: UUID
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)


class UnitUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    number: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class SectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    section_type: str = Field(min_length=1, max_length=80)
    position: int = Field(ge=1)


class ActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: str | None = Field(default=None, max_length=30)
    activity_type: str = Field(min_length=1, max_length=80)
    instruction: str | None = None


class FragmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_document_id: UUID
    activity_id: UUID
    pdf_page: int = Field(ge=0)
    printed_page: int | None = Field(default=None, ge=0)
    normalized_text: str = Field(min_length=1)


class FragmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    activity_id: UUID | None = None
    pdf_page: int | None = Field(default=None, ge=0)
    printed_page: int | None = Field(default=None, ge=0)
    normalized_text: str | None = Field(default=None, min_length=1)
    review_status: Literal["draft", "verified", "rejected"] | None = None


class SectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    section_type: str | None = Field(default=None, min_length=1, max_length=80)
    position: int | None = Field(default=None, ge=1)


class ActivityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    number: str | None = Field(default=None, max_length=30)
    activity_type: str | None = Field(default=None, min_length=1, max_length=80)
    instruction: str | None = None


def _context(request: Request) -> dict[str, str | None]:
    return {"request_id": getattr(request.state, "trace_id", None), "ip_address": request.client.host if request.client else None, "platform": request.headers.get("x-client-platform")}


@router.get("/units")
def list_units(_admin: AdminUser, service: ContentService) -> dict[str, Any]:
    return {"items": service.list_units()}


@router.post("/units", status_code=201)
def create_unit(payload: UnitCreate, request: Request, admin: AdminUser, service: ContentService):
    return service.create_unit(**payload.model_dump(), actor_id=admin.id, **_context(request))


@router.patch("/units/{unit_id}")
def update_unit(unit_id: UUID, payload: UnitUpdate, request: Request, admin: AdminUser, service: ContentService):
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_version")
    return service.update_unit(unit_id, data, expected_version=expected, actor_id=admin.id, **_context(request))


@router.post("/units/{unit_id}/publish")
def publish_unit(unit_id: UUID, payload: VersionRequest, request: Request, admin: AdminUser, service: ContentService):
    return service.publish_unit(unit_id, expected_version=payload.expected_version, actor_id=admin.id, **_context(request))


@router.post("/units/{unit_id}/archive")
def archive_unit(unit_id: UUID, request: Request, admin: AdminUser, service: ContentService):
    return service.archive_unit(unit_id, actor_id=admin.id, **_context(request))


@router.delete("/units/{unit_id}", status_code=204)
def delete_unit(unit_id: UUID, request: Request, admin: AdminUser, service: ContentService) -> Response:
    service.delete_unit(unit_id, actor_id=admin.id, **_context(request))
    return Response(status_code=204)


@router.post("/units/{unit_id}/sections", status_code=201)
def create_section(unit_id: UUID, payload: SectionCreate, request: Request, admin: AdminUser, service: ContentService):
    return service.create_section(unit_id, **payload.model_dump(), actor_id=admin.id, **_context(request))


@router.get("/units/{unit_id}/sections")
def list_sections(unit_id: UUID, _admin: AdminUser, service: ContentService):
    return {"items": service.list_sections(unit_id)}


@router.patch("/sections/{section_id}")
def update_section(section_id: UUID, payload: SectionUpdate, request: Request, admin: AdminUser, service: ContentService):
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_version")
    return service.update_section(section_id, data, expected_version=expected, actor_id=admin.id, **_context(request))


@router.delete("/sections/{section_id}", status_code=204)
def delete_section(section_id: UUID, request: Request, admin: AdminUser, service: ContentService) -> Response:
    service.delete_section(section_id, actor_id=admin.id, **_context(request))
    return Response(status_code=204)


@router.post("/sections/{section_id}/activities", status_code=201)
def create_activity(section_id: UUID, payload: ActivityCreate, request: Request, admin: AdminUser, service: ContentService):
    return service.create_activity(section_id, **payload.model_dump(), actor_id=admin.id, **_context(request))


@router.get("/sections/{section_id}/activities")
def list_activities(section_id: UUID, _admin: AdminUser, service: ContentService):
    return {"items": service.list_activities(section_id)}


@router.patch("/activities/{activity_id}")
def update_activity(activity_id: UUID, payload: ActivityUpdate, request: Request, admin: AdminUser, service: ContentService):
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_version")
    return service.update_activity(activity_id, data, expected_version=expected, actor_id=admin.id, **_context(request))


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(activity_id: UUID, request: Request, admin: AdminUser, service: ContentService) -> Response:
    service.delete_activity(activity_id, actor_id=admin.id, **_context(request))
    return Response(status_code=204)


@router.post("/fragments", status_code=201)
def create_fragment(payload: FragmentCreate, request: Request, admin: AdminUser, service: ContentService):
    return service.create_fragment(**payload.model_dump(), actor_id=admin.id, **_context(request))


@router.get("/fragments")
def list_fragments(_admin: AdminUser, service: ContentService, activity_id: UUID | None = None):
    return {"items": service.list_fragments(activity_id)}


@router.patch("/fragments/{fragment_id}")
def update_fragment(fragment_id: UUID, payload: FragmentUpdate, request: Request, admin: AdminUser, service: ContentService):
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_version")
    return service.update_fragment(fragment_id, data, expected_version=expected, actor_id=admin.id, **_context(request))


@router.post("/fragments/{fragment_id}/publish")
def publish_fragment(fragment_id: UUID, payload: VersionRequest, request: Request, admin: AdminUser, service: ContentService):
    return service.publish_fragment(fragment_id, expected_version=payload.expected_version, actor_id=admin.id, **_context(request))


@router.post("/fragments/{fragment_id}/archive")
def archive_fragment(fragment_id: UUID, request: Request, admin: AdminUser, service: ContentService):
    return service.archive_fragment(fragment_id, actor_id=admin.id, **_context(request))


@router.delete("/fragments/{fragment_id}", status_code=204)
def delete_fragment(fragment_id: UUID, request: Request, admin: AdminUser, service: ContentService) -> Response:
    service.delete_fragment(fragment_id, actor_id=admin.id, **_context(request))
    return Response(status_code=204)


@router.post("/{entity_type}/{entity_id}/preview")
def preview(entity_type: Literal["unit", "section", "activity", "fragment"], entity_id: UUID, _admin: AdminUser, service: ContentService):
    return service.preview(entity_type, entity_id)


@router.get("/{entity_type}/{entity_id}/versions")
def versions(entity_type: Literal["unit", "section", "activity", "fragment"], entity_id: UUID, _admin: AdminUser, service: ContentService):
    return {"items": service.versions(entity_type, entity_id)}


@router.post("/{entity_type}/{entity_id}/restore/{version}")
def restore(entity_type: Literal["unit", "fragment"], entity_id: UUID, version: int, request: Request, admin: AdminUser, service: ContentService):
    return service.restore(entity_type, entity_id, version=version, actor_id=admin.id, **_context(request))
