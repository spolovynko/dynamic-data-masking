from fastapi import APIRouter

from apps.api.schemas.health import HealthResponse
from ddm_engine.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.app_version,
        environment=settings.environment,
    )
