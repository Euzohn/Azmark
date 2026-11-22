from fastapi import APIRouter, Depends

from app.api.deps import refresh_record_statuses
from app.api.routes import (
    activities,
    admin,
    ai,
    attachments,
    audit,
    auth,
    dashboard,
    data_sources,
    data_transfer,
    expenses,
    flights,
    health,
    hotels,
    notes,
    pending_actions,
    photos,
    places,
    records,
    reference,
    settings,
    tokens,
    trains,
    transports,
    trips,
)

api_router = APIRouter()
# Routers exposing record/hotel/trip statuses advance overdue rows on access
# (scheduled → completed, planned → ongoing → completed); see status_refresh.
_status_routers = {"dependencies": [Depends(refresh_record_statuses)]}
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(flights.router, **_status_routers)
api_router.include_router(trains.router, **_status_routers)
api_router.include_router(transports.router, **_status_routers)
api_router.include_router(hotels.router, **_status_routers)
api_router.include_router(places.router)
api_router.include_router(activities.router)
api_router.include_router(expenses.router)
api_router.include_router(notes.router)
api_router.include_router(photos.router)
api_router.include_router(records.router, **_status_routers)
api_router.include_router(attachments.router)
api_router.include_router(reference.router)
api_router.include_router(settings.router)
api_router.include_router(tokens.router)
api_router.include_router(pending_actions.router)
api_router.include_router(audit.router)
api_router.include_router(trips.router, **_status_routers)
api_router.include_router(dashboard.router, **_status_routers)
api_router.include_router(ai.router)
api_router.include_router(data_transfer.router, **_status_routers)
api_router.include_router(data_sources.router)
