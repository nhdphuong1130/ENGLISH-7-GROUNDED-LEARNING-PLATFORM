from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from english7.db.session import get_session_factory
from english7.modules.admin.dashboard_service import AdminDashboardService
from english7.modules.admin.dependencies import AdminUser


router = APIRouter(tags=["admin-dashboard"])


class AdminDashboardResponse(BaseModel):
    total_students: int
    active_students: int
    locked_students: int
    archived_students: int
    submitted_tests: int
    draft_content: int


def get_admin_dashboard_service() -> AdminDashboardService:
    return AdminDashboardService(get_session_factory())


DashboardService = Annotated[
    AdminDashboardService,
    Depends(get_admin_dashboard_service),
]


@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    _admin: AdminUser,
    service: DashboardService,
) -> AdminDashboardResponse:
    return AdminDashboardResponse(**service.summary())
