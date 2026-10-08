from fastapi import APIRouter

from app.api.routes import audit, auth, flights, health, reference, settings, trips

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(flights.router)
api_router.include_router(reference.router)
api_router.include_router(settings.router)
api_router.include_router(audit.router)
api_router.include_router(trips.router)
