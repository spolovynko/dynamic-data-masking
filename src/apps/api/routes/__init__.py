from fastapi import APIRouter

from apps.api.routes.detections import router as detections_router
from apps.api.routes.documents import router as documents_router
from apps.api.routes.downloads import router as downloads_router
from apps.api.routes.health import router as health_router
from apps.api.routes.jobs import router as jobs_router
from apps.api.routes.metrics import router as metrics_router
from apps.api.routes.plans import router as plans_router
from apps.api.routes.quality import router as quality_router
from apps.api.routes.texts import router as texts_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(jobs_router)
api_router.include_router(detections_router)
api_router.include_router(plans_router)
api_router.include_router(quality_router)
api_router.include_router(downloads_router)
api_router.include_router(texts_router)
api_router.include_router(metrics_router)
