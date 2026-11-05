from fastapi import APIRouter

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
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(flights.router)
api_router.include_router(trains.router)
api_router.include_router(transports.router)
api_router.include_router(hotels.router)
api_router.include_router(places.router)
api_router.include_router(activities.router)
api_router.include_router(expenses.router)
api_router.include_router(notes.router)
api_router.include_router(records.router)
api_router.include_router(attachments.router)
api_router.include_router(reference.router)
api_router.include_router(settings.router)
api_router.include_router(tokens.router)
api_router.include_router(pending_actions.router)
api_router.include_router(audit.router)
api_router.include_router(trips.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai.router)
api_router.include_router(data_transfer.router)
api_router.include_router(data_sources.router)
