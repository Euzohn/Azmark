"""Dashboard, statistics, timeline and map endpoints (spec #10, #28, #26, #27)."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_dashboard_service
from app.models.user import User
from app.schemas.dashboard import DashboardRead, MapRoutesRead, StatisticsRead
from app.schemas.transport import FlightRead
from app.services.dashboard import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardRead:
    return service.overview(user_id=current_user.id)


@router.get("/statistics", response_model=StatisticsRead)
def statistics(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> StatisticsRead:
    return service.statistics(user_id=current_user.id)


@router.get("/timeline", response_model=list[FlightRead])
def timeline(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> list[FlightRead]:
    return service.timeline(user_id=current_user.id)


@router.get("/map/routes", response_model=MapRoutesRead)
def map_routes(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> MapRoutesRead:
    return service.routes(user_id=current_user.id)
