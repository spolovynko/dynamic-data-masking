from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

router = APIRouter(include_in_schema=False)


def frontend_root() -> Path:
    cwd_frontend = Path.cwd() / "frontend"
    if cwd_frontend.exists():
        return cwd_frontend
    return Path(__file__).resolve().parents[3] / "frontend"


def frontend_assets() -> StaticFiles:
    return StaticFiles(directory=frontend_root())


@router.get("/")
def index() -> FileResponse:
    return FileResponse(frontend_root() / "index.html")
