from fastapi import APIRouter

from apps.api.routes.documents import router as documents_router
from apps.api.routes.health import router as health_router
from apps.api.routes.jobs import router as jobs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(jobs_router)
