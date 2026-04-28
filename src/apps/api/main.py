from fastapi import FastAPI

from apps.api.frontend import frontend_assets
from apps.api.frontend import router as frontend_router
from apps.api.routes import api_router
from ddm_engine.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Detect and redact sensitive data from uploaded documents.",
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(frontend_router)
    app.mount("/assets", frontend_assets(), name="frontend-assets")
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "apps.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
